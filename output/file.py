import json
import os

from telethon.utils import get_display_name


class Writer:
    def __init__(self, config: dict):
        self.path = os.path.expanduser(config.get("path"))

    async def write_message(self, message):
        sender_user = await message.get_sender()

        data = {
            "id": message.id,
            "date": message.date.isoformat(),
            "sender": {
                "username": sender_user.username,
                "firstName": sender_user.first_name,
                "lastName": sender_user.last_name,
            },
            "chat": get_display_name(await message.get_chat()),
            "message": message.text
        }

        with open(self.path, "a") as output_file:
            json.dump(data, output_file)
            output_file.write("\n")
