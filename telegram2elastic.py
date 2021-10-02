#! /usr/bin/env python3

import argparse
import asyncio
import logging
import os
import yaml

from datetime import datetime
from elasticsearch import Elasticsearch
from telethon import TelegramClient, events
from telethon.tl.types import User, Chat, Channel
from telethon.utils import get_display_name

LOG_LEVEL_INFO = 35

config = {}


def get_config(path: str, default=None, required=True):
    value = config

    for part in path.split("."):
        if value is None or part not in value:
            if required and default is None:
                raise KeyError("Config option {} not found in config file!".format(path))
            else:
                return default

        value = value.get(part)

    if value is None:
        value = default

    return value


def get_chat_type(chat):
    if isinstance(chat, Chat):
        if chat.deactivated:
            return None
        else:
            return "group"

    if isinstance(chat, Channel):
        if chat.megagroup:
            return "group"
        else:
            return "channel"

    if isinstance(chat, User):
        if chat.bot:
            return "bot"

        if chat.contact:
            return "contact"
        else:
            return "user"

    return None


def is_chat_enabled(chat, chat_types=None):
    additional_chats = get_config("telegram.additional_chats", [])

    if chat.id in additional_chats:
        return True

    if chat_types is None:
        chat_types = get_config("telegram.chat_types", [])

    chat_type = get_chat_type(chat)
    if chat_type is None:
        return False

    return chat_type in chat_types


def prepare_chats(chats):
    if isinstance(chats, list):
        prepared_chats = []

        for chat in chats:
            prepared_chats.append(prepare_chats(chat))

        return prepared_chats
    else:
        if chats.startswith("@"):
            chats = chats[1:]
        else:
            chats = int(chats)

        return chats


async def get_chats(tg_client, chat_types=None):
    chats = []

    for dialog in await tg_client.get_dialogs():
        if not is_chat_enabled(dialog.entity, chat_types):
            continue

        chats.append(dialog.entity)

    return chats


async def index_message(es_client, message):
    chat = await message.get_chat()
    chat_display_name = get_display_name(chat)

    if not is_chat_enabled(chat):
        logging.debug("Skipping message {} from chat '{}' as chat type {} is not enabled".format(message.id, chat_display_name, get_chat_type(chat)))
        return

    sender_user = await message.get_sender()

    doc_data = {
        "timestamp": message.date,
        "sender": {
            "username": sender_user.username,
            "firstName": sender_user.first_name,
            "lastName": sender_user.last_name,
        },
        "chat": chat_display_name,
        "message": message.text
    }

    index_date_format = get_config("elasticsearch.index.date_format", required=False)
    index_prefix = get_config("elasticsearch.index.prefix", "telegram")
    if index_date_format is None:
        index_name = index_prefix
    else:
        index_name = "-".join([index_prefix, message.date.strftime(index_date_format)])

    es_client.index(index_name, body=doc_data, id=message.id)


async def listen_for_events(tg_client, es_client):
    @tg_client.on(events.NewMessage())
    @tg_client.on(events.MessageEdited())
    async def handler(event):
        await index_message(es_client, event.message)

    await tg_client.catch_up()


async def task(tg_client, es_client, arguments):
    if arguments.command == "import-history":
        if arguments.start_date:
            offset_date = datetime.strptime(arguments.start_date, "%Y-%m-%d")
        else:
            offset_date = None

        if arguments.chats:
            chats = await tg_client.get_entity(prepare_chats(arguments.chats))
        else:
            chats = await get_chats(tg_client)

        for chat in chats:
            display_name = get_display_name(chat)

            if offset_date:
                logging.log(LOG_LEVEL_INFO, "Importing history for chat '{}' starting at {}".format(display_name, offset_date.strftime("%c")))
            else:
                logging.log(LOG_LEVEL_INFO, "Importing full history for chat '{}'".format(display_name))

            async for message in tg_client.iter_messages(chat, offset_date=offset_date, reverse=True):
                await index_message(es_client, message)

        logging.log(LOG_LEVEL_INFO, "Import finished")
    elif arguments.command == "list-chats":
        for chat in await get_chats(tg_client, arguments.types):
            print(chat.id, get_display_name(chat), get_chat_type(chat))
    elif arguments.command == "listen":
        await listen_for_events(tg_client, es_client)


def main():
    global config

    argument_parser = argparse.ArgumentParser(description="A simple Telegram client writing chat messages to an Elasticsearch instance in realtime")

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

    elasticsearch_username = get_config("elasticsearch.username", required=False)
    elasticsearch_password = get_config("elasticsearch.password", required=False)

    if elasticsearch_username is not None and elasticsearch_password is not None:
        elasticsearch_httpauth = [elasticsearch_username, elasticsearch_password]
    else:
        elasticsearch_httpauth = None

    tg_client = TelegramClient(session=os.path.expanduser(get_config("telegram.session_file")), api_id=get_config("telegram.api_id"), api_hash=get_config("telegram.api_hash"))
    es_client = Elasticsearch(hosts=get_config("elasticsearch.host", "localhost"), http_auth=elasticsearch_httpauth)

    with tg_client:
        if arguments.command == "listen":
            loop = asyncio.get_event_loop()
            loop.create_task(task(tg_client, es_client, arguments))

            try:
                loop.run_forever()
            except KeyboardInterrupt:
                pass
        else:
            tg_client.loop.run_until_complete(task(tg_client, es_client, arguments))


if __name__ == "__main__":
    main()
