#! /usr/bin/env python3

import argparse
import asyncio
import base64
import importlib
import logging
import os
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

import yaml

from datetime import datetime
from telethon import TelegramClient, events
from telethon.tl import types
from telethon.tl.functions.messages import TranslateTextRequest
from telethon.tl.patched import Message
from telethon.tl.types import User, Chat, Channel
from telethon.tl.types.messages import TranslateResultText
from telethon.utils import get_display_name

LOG_LEVEL_INFO = 35


class FileSize:
    units = ["K", "M", "G", "T", "P"]

    @staticmethod
    def human_readable_to_bytes(size_string: str):
        # Convert to uppercase and strip "B" suffix (i.e. "mb" or "MB" will be "M")
        size_string = size_string.upper().rstrip("B")

        # Size is already in bytes
        if size_string.isdigit():
            return int(size_string)

        size_bytes = size_string[:-1]
        unit_index = FileSize.units.index(size_string[-1]) + 1

        return int(float(size_bytes) * pow(1024, unit_index))

    @staticmethod
    def bytes_to_human_readable(size_bytes: int):
        unit = ""

        for unit in [""] + FileSize.units:
            if abs(size_bytes) < 1024:
                return f"{size_bytes:3.1f}{unit}B"
            size_bytes /= 1024

        return f"{size_bytes:3.1f}{unit}B"


class DottedPathDict(dict):
    def get(self, path, default=None):
        path = path.split(".", 1)

        key = path.pop(0)

        if key not in self:
            return default

        if not path:
            return super().get(key)

        nested_dict = self[key]

        if not isinstance(nested_dict, DottedPathDict):
            return default

        return nested_dict.get(path[0], default)

    def set(self, path, value):
        path = path.split(".", 1)

        key = path.pop(0)

        if not path:
            self[key] = value
            return

        new_dict = DottedPathDict()
        self[key] = new_dict

        new_dict.set(path[0], value)


def json_default(value):
    if isinstance(value, bytes):
        return base64.b64encode(value).decode("ascii")
    elif isinstance(value, datetime):
        return value.isoformat()
    else:
        return repr(value)


async def async_exec(code, variables):
    task = [None]

    exec_variables = {
        "asyncio": asyncio,
        "task": task
    }

    exec_variables.update(variables)
    exec("async def _async_exec():\n return {}\ntask[0] = asyncio.ensure_future(_async_exec())".format(code), exec_variables)
    return await task[0]


async def eval_map(input_map: dict, variables: dict):
    output = DottedPathDict()

    for key, expression in input_map.items():
        output.set(key, await async_exec(expression, variables))

    return output


@dataclass
class DownloadedMedia:
    filepath: Path
    filename: str


class MediaConfigurationRule:
    def __init__(self, global_config: dict, config_data: dict, rule_index: int):
        self.global_config = global_config
        self.config_data = config_data

        self.logger = logging.getLogger(f"media_download_config_rule[#{rule_index}]")

    def matches_message(self, message, chat):
        if isinstance(message.media, types.MessageMediaPhoto):
            message_media_type = "photo"
        else:
            message_media_type = "file"

        if not self.matches_media_type(message_media_type):
            return False

        if not self.matches_mime_type(message.file.mime_type):
            return False

        message_chat_type = ChatType.get_from_chat(chat)
        if message_chat_type is None or not self.matches_chat_type(message_chat_type.value):
            return False

        message_chat_id = message.chat_id
        if message_chat_id is None or not self.matches_chat_id(message_chat_id):
            return False

        if not self.check_size_limit(message.file.size):
            return False

        return True

    def matches_media_type(self, media_type: str):
        return self.matches_config_value("media_type", media_type)

    def matches_mime_type(self, mime_type: str):
        return self.matches_config_value("mime_type", mime_type)

    def matches_chat_type(self, chat_type: str):
        return self.matches_config_value("chat_type", chat_type)

    def matches_chat_id(self, chat_id: int):
        chat_ids = self.config_data.get("chats")
        if not chat_ids:
            return True

        self.logger.debug(f"Checking chat ID {chat_id} in {chat_ids}")

        return chat_id in chat_ids

    def check_size_limit(self, file_size_bytes: int):
        max_size = self.get_max_size()
        if max_size == "":
            return True

        max_size_bytes = FileSize.human_readable_to_bytes(max_size)
        file_size_string = FileSize.bytes_to_human_readable(file_size_bytes)

        self.logger.debug(f"Checking file size {file_size_string} <= {max_size}")

        return file_size_bytes <= max_size_bytes

    def get_download_path(self) -> str | None:
        return self.get_with_fallback("download_path")

    def get_filepattern(self) -> str:
        return self.get_with_fallback("file_pattern", "{date[year]}-{date[month]}-{date[day]}_{date[hour]}-{date[minute]}-{date[second]}_{message[id]}_{file[name]}.{file[ext]}")

    def get_max_size(self) -> str:
        return self.get_with_fallback("max_size", "")

    def matches_config_value(self, config_name: str, value):
        match_exact_value = self.config_data.get(config_name)
        match_regex_value = self.config_data.get(f"{config_name}_re")

        if match_exact_value is None and match_regex_value is None:
            return True

        self.logger.debug(f"Checking config '{config_name}' with value '{value}': exact = {match_exact_value}, regex = {match_regex_value}")

        if match_exact_value is not None and match_exact_value == value:
            return True

        if match_regex_value is not None and re.match(match_regex_value, value):
            return True

        return False

    def get_with_fallback(self, option_name: str, default_value=None):
        value = self.config_data.get(option_name)
        if value is not None:
            self.logger.debug(f"Config for '{option_name}' resolved: {value}")
            return value

        # Fallback to global config
        value = self.global_config.get(option_name)
        if value is not None:
            self.logger.debug(f"Config for '{option_name}' resolved to global config: {value}")
            return value

        self.logger.debug(f"Config for '{option_name}' resolved to default: {default_value}")

        return default_value


class MediaConfiguration:
    def __init__(self, config: dict):
        self.config = config

        self.rules = []

        for index, rule in enumerate(config.get("rules", [])):
            self.rules.append(MediaConfigurationRule(self.config, rule, index))

        # Add default match-all rule if there are no rules configured
        if not self.rules:
            self.rules.append(MediaConfigurationRule(self.config, {}, 0))

    def get_rule(self, message, chat):
        for rule in self.rules:
            if rule.matches_message(message, chat):
                rule.logger.debug("Rule matches")
                return rule
            else:
                rule.logger.debug("Rule does not match")


class OutputWriter(ABC):
    def __init__(self, config: dict):
        self.config: dict = config

    @abstractmethod
    async def write_message(self, message, translated_text: str | None, downloaded_media: DownloadedMedia):
        pass

    async def get_message_dict(self, message, translated_text: str | None, downloaded_media: DownloadedMedia):
        sender_user = await message.get_sender()

        if sender_user is None:
            sender = None
        elif isinstance(sender_user, Channel):
            sender = {
                "username": sender_user.username,
                "firstName": sender_user.title,
                "lastName": None
            }
        else:
            sender = {
                "username": sender_user.username,
                "firstName": sender_user.first_name,
                "lastName": sender_user.last_name
            }

        output_map_config = self.config.get("output_map")

        if output_map_config is None:
            output_map_config = {
                "id": "message.id",
                "date": "message.date",
                "sender": "sender",
                "chat": "get_display_name(await message.get_chat())",
                "message": "message.text",
                "media": "media.filename if media else None"
            }

        return await eval_map(output_map_config, {
            "message": message,
            "sender": sender,
            "get_display_name": get_display_name,
            "translated_text": translated_text,
            "media": downloaded_media
        })


class ChatType(Enum):
    GROUP = "group"
    CHANNEL = "channel"
    BOT = "bot"
    CONTACT = "contact"
    USER = "user"

    @classmethod
    def get_from_chat(cls, chat):
        if isinstance(chat, Chat):
            if chat.deactivated:
                return None
            else:
                return cls.GROUP

        if isinstance(chat, Channel):
            if chat.megagroup:
                return cls.GROUP
            else:
                return cls.CHANNEL

        if isinstance(chat, User):
            if chat.bot:
                return cls.BOT

            if chat.contact:
                return cls.CONTACT
            else:
                return cls.USER

        return None


class OutputHandler:
    def __init__(self, media_config: dict, translate_to_lang: str = None):
        self.outputs = []
        self.imports = {}
        self.media_config = MediaConfiguration(media_config)
        self.translate_to_lang = translate_to_lang

    def add(self, config: dict):
        output_type = config.get("type")
        del config["type"]

        if output_type not in self.imports:
            self.imports[output_type] = importlib.import_module("output.{}".format(output_type))

        self.outputs.append(self.imports[output_type].Writer(config))

    async def write_message(self, message, is_chat_enabled: callable):
        # message might not be an actual message (i.e. MessageService)
        if not isinstance(message, Message):
            return

        chat = await message.get_chat()
        chat_display_name = get_display_name(chat)

        if not is_chat_enabled(chat):
            chat_type = ChatType.get_from_chat(chat)

            logging.debug("Skipping message {} from chat '{}' as chat type {} is not enabled".format(message.id, chat_display_name, chat_type.value if chat_type else None))
            return

        if message.file:
            downloaded_media = await self.download_media(message)
        else:
            downloaded_media = None

        if self.translate_to_lang and message.text:
            try:
                translate_text_result: TranslateResultText = await message.client(TranslateTextRequest(to_lang=self.translate_to_lang, peer=message.input_sender, msg_id=message.id))
                translated_text = translate_text_result.text
            except BaseException as exception:
                logging.error(f"Unable to translate text '{message.text}' using language '{self.translate_to_lang}': {exception}")
                translated_text = None
        else:
            translated_text = None

        for output in self.outputs:
            await output.write_message(message=message, translated_text=translated_text, downloaded_media=downloaded_media)

    async def download_media(self, message):
        if message.file.name is None:
            original_filename = f"msg{message.chat_id}-{message.id}"
        else:
            original_filename = Path(message.file.name).stem

        full_original_filename = f"{original_filename}{message.file.ext}"

        config_rule = self.media_config.get_rule(message, await message.get_chat())
        if config_rule is None:
            logging.debug(f"Skipping media download for '{full_original_filename}' as no config rule matches (mime_type: {message.file.mime_type})")
            return

        download_path = config_rule.get_download_path()
        if download_path is None:
            logging.debug(f"Skipping media download for '{full_original_filename}' as no download path has been configured")
            return

        download_path = Path(download_path).expanduser()

        filename_pattern_map = {
            "date": {
                "year": message.date.year,
                "month": str(message.date.month).rjust(2, "0"),
                "day": str(message.date.day).rjust(2, "0"),
                "hour": str(message.date.hour).rjust(2, "0"),
                "minute": str(message.date.minute).rjust(2, "0"),
                "second": str(message.date.second).rjust(2, "0")
            },
            "file": {
                "name": original_filename,
                "ext": message.file.ext.strip(".")
            },
            "message": {
                "id": message.id,
                "chat_id": message.chat_id
            }
        }

        filename = config_rule.get_filepattern().format_map(filename_pattern_map)
        filepath = download_path.joinpath(filename)
        file_size_string = FileSize.bytes_to_human_readable(message.file.size)

        logging.debug(f"Downloading media file '{full_original_filename}' to {filepath} ({file_size_string})")
        filepath.parent.mkdir(parents=True, exist_ok=True)
        await message.download_media(file=filepath)

        return DownloadedMedia(filepath=filepath, filename=filename)


class TelegramReader:
    def __init__(self, config: dict, output_handler: OutputHandler):
        self.client = TelegramClient(session=os.path.expanduser(config.get("session_file")), api_id=config.get("api_id"), api_hash=config.get("api_hash"))
        self.output_handler = output_handler
        self.additional_chats = config.get("additional_chats", [])
        self.chat_types = config.get("chat_types", [])

    async def import_history(self, start_date, chats):
        if start_date:
            offset_date = datetime.strptime(start_date, "%Y-%m-%d")
        else:
            offset_date = None

        if chats:
            chats = await self.client.get_entity(TelegramReader.prepare_chats(chats))
        else:
            chats = await self.get_chats()

        for chat in chats:
            display_name = get_display_name(chat)

            if offset_date:
                logging.log(LOG_LEVEL_INFO, "Importing history for chat '{}' starting at {}".format(display_name, offset_date.strftime("%c")))
            else:
                logging.log(LOG_LEVEL_INFO, "Importing full history for chat '{}'".format(display_name))

            async for message in self.client.iter_messages(chat, offset_date=offset_date, reverse=True):
                await self.output_handler.write_message(message, self.is_chat_enabled)

        logging.log(LOG_LEVEL_INFO, "Import finished")

    async def list_chats(self, types):
        for chat in await self.get_chats(types):
            chat_type = ChatType.get_from_chat(chat)

            print(chat.id, get_display_name(chat), chat_type.value if chat_type else None)

    async def listen(self):
        logging.log(LOG_LEVEL_INFO, "Listening for events")

        @self.client.on(events.NewMessage())
        @self.client.on(events.MessageEdited())
        async def handler(event):
            await self.output_handler.write_message(event.message, self.is_chat_enabled)

        await self.client.catch_up()

    def is_chat_enabled(self, chat, chat_types=None):
        if chat.id in self.additional_chats:
            return True

        if chat_types is None:
            chat_types = self.chat_types

        chat_type = ChatType.get_from_chat(chat)
        if chat_type is None:
            return False

        return chat_type.value in chat_types

    async def get_chats(self, chat_types=None):
        chats = []

        for dialog in await self.client.get_dialogs():
            if self.is_chat_enabled(dialog.entity, chat_types):
                chats.append(dialog.entity)

        return chats

    @staticmethod
    def prepare_chats(chats):
        if isinstance(chats, list):
            prepared_chats = []

            for chat in chats:
                prepared_chats.append(TelegramReader.prepare_chats(chat))

            return prepared_chats
        else:
            if chats.startswith("@"):
                chats = chats[1:]
            else:
                chats = int(chats)

            return chats


def main():
    argument_parser = argparse.ArgumentParser(description="A simple Telegram client writing chat messages to multiple outputs in realtime")

    argument_parser.add_argument("--config", "-c", help="path to your config file", default=os.getenv("CONFIG_FILE", "config.yml"))
    argument_parser.add_argument("--debug", "-d", help="print debug output", action="store_true")

    sub_command_parser = argument_parser.add_subparsers(dest="command", required=True)

    sub_command_parser.add_parser("listen")

    import_history_command = sub_command_parser.add_parser("import-history")
    import_history_command.add_argument("start_date", nargs="?", help="the start date at which to start importing (in format YYYY-MM-DD)")
    import_history_command.add_argument("--chats", nargs="*", help="only import the given chats (use list-chats to get IDs)")

    list_chats_command = sub_command_parser.add_parser("list-chats")
    list_chats_command.add_argument("--types", nargs="*", choices=["contact", "user", "group", "channel"], help="list the given chat types instead of those from the config file")

    arguments = argument_parser.parse_args()

    logging.basicConfig(format="[%(levelname) 5s/%(asctime)s] %(name)s: %(message)s", level=logging.DEBUG if arguments.debug else logging.WARNING)
    logging.addLevelName(LOG_LEVEL_INFO, "INFO")

    with open(arguments.config, "r") as config_file:
        config = yaml.safe_load(config_file)

    if not isinstance(config, dict):
        logging.error("Unable to parse config file '{}'".format(arguments.config))
        exit(1)

    output_handler = OutputHandler(media_config=config.get("media", {}), translate_to_lang=config.get("translate_to_lang"))

    for output in config.get("outputs", []):
        output_handler.add(output)

    telegram_reader = TelegramReader(config.get("telegram", {}), output_handler)

    with telegram_reader.client:
        loop = telegram_reader.client.loop

        if arguments.command == "import-history":
            loop.run_until_complete(telegram_reader.import_history(arguments.start_date, arguments.chats))
        elif arguments.command == "list-chats":
            loop.run_until_complete(telegram_reader.list_chats(arguments.types))
        elif arguments.command == "listen":
            loop.create_task(telegram_reader.listen())

            try:
                loop.run_forever()
            except KeyboardInterrupt:
                pass


if __name__ == "__main__":
    main()
