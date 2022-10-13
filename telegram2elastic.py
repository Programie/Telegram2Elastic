#! /usr/bin/env python3

import argparse
import asyncio
import importlib
import logging
import os
from enum import Enum

import yaml

from datetime import datetime
from telethon import TelegramClient, events
from telethon.tl.types import User, Chat, Channel
from telethon.utils import get_display_name

LOG_LEVEL_INFO = 35


async def get_message_dict(message):
    sender_user = await message.get_sender()

    if isinstance(sender_user, Channel):
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

    return {
        "id": message.id,
        "date": message.date,
        "sender": sender,
        "chat": get_display_name(await message.get_chat()),
        "message": message.text
    }


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
    def __init__(self):
        self.outputs = []
        self.imports = {}

    def add(self, config: dict):
        output_type = config.get("type")
        del config["type"]

        if output_type not in self.imports:
            self.imports[output_type] = importlib.import_module("output.{}".format(output_type))

        self.outputs.append(self.imports[output_type].Writer(config))

    async def write_message(self, message, is_chat_enabled: callable):
        chat = await message.get_chat()
        chat_display_name = get_display_name(chat)

        if not is_chat_enabled(chat):
            chat_type = ChatType.get_from_chat(chat)

            logging.debug("Skipping message {} from chat '{}' as chat type {} is not enabled".format(message.id, chat_display_name, chat_type.value if chat_type else None))
            return

        for output in self.outputs:
            await output.write_message(message)


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

    sub_command_parser = argument_parser.add_subparsers(dest="command", required=True)

    sub_command_parser.add_parser("listen")

    import_history_command = sub_command_parser.add_parser("import-history")
    import_history_command.add_argument("start_date", nargs="?", help="the start date at which to start importing (in format YYYY-MM-DD)")
    import_history_command.add_argument("--chats", nargs="*", help="only import the give chats (use list-chats to get IDs)")

    list_chats_command = sub_command_parser.add_parser("list-chats")
    list_chats_command.add_argument("--types", nargs="*", choices=["contact", "user", "group", "channel"], help="list the given chat types instead of those from the config file")

    arguments = argument_parser.parse_args()

    logging.basicConfig(format="[%(levelname) 5s/%(asctime)s] %(name)s: %(message)s", level=logging.WARNING)
    logging.addLevelName(LOG_LEVEL_INFO, "INFO")

    with open(arguments.config, "r") as config_file:
        config = yaml.safe_load(config_file)

    if not isinstance(config, dict):
        logging.error("Unable to parse config file '{}'".format(arguments.config))
        exit(1)

    output_handler = OutputHandler()

    for output in config.get("outputs", []):
        output_handler.add(output)

    telegram_reader = TelegramReader(config.get("telegram", {}), output_handler)

    with telegram_reader.client:
        if arguments.command == "import-history":
            telegram_reader.client.loop.run_until_complete(telegram_reader.import_history(arguments.start_date, arguments.chats))
        elif arguments.command == "list-chats":
            telegram_reader.client.loop.run_until_complete(telegram_reader.list_chats(arguments.types))
        elif arguments.command == "listen":
            loop = asyncio.new_event_loop()
            loop.create_task(telegram_reader.listen())

            try:
                loop.run_forever()
            except KeyboardInterrupt:
                pass


if __name__ == "__main__":
    main()
