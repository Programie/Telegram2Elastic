import json
import logging
import socket
import time

from telegram2elastic import json_default, OutputWriter


class Writer(OutputWriter):
    def __init__(self, config: dict):
        super().__init__(config)

        self.host = config.get("host")
        self.port = config.get("port")

        self.socket = None

    def ensure_connected(self):
        if self.socket:
            return

        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.connect((self.host, self.port))

    async def write_message(self, message):
        message_dict = await self.get_message_dict(message)

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
