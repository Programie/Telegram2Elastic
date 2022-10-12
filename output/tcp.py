import json
import logging
import socket
import time

from telethon.utils import get_display_name


class Writer:
    def __init__(self, config: dict):
        self.host = config.get("host")
        self.port = config.get("port")

        self.socket = None

    def ensure_connected(self):
        if self.socket:
            return

        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.connect((self.host, self.port))

    async def write_message(self, message):
        sender_user = await message.get_sender()

        data = json.dumps({
            "id": message.id,
            "date": message.date.isoformat(),
            "sender": {
                "username": sender_user.username,
                "firstName": sender_user.first_name,
                "lastName": sender_user.last_name,
            },
            "chat": get_display_name(await message.get_chat()),
            "message": message.text
        }) + "\n"

        while True:
            try:
                self.ensure_connected()
                self.socket.sendall(bytes(data, encoding="utf-8"))
                break
            except Exception as exception:
                logging.error(exception)
                self.socket.close()
                self.socket = None
                time.sleep(1)
