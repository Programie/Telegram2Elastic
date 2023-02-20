import json
import logging
import socket
import time

from telegram2elastic import get_message_dict, json_default


class Writer:
    def __init__(self, config: dict):
        self.host = config.get("host")
        self.port = config.get("port")
        self.output_map = config.get("output_map")

        self.socket = None

    def ensure_connected(self):
        if self.socket:
            return

        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.connect((self.host, self.port))

    async def write_message(self, message):
        message_dict = await get_message_dict(message, self.output_map)

        data = json.dumps(message_dict, default=json_default) + "\n"

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
