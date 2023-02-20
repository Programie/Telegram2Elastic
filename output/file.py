import json
import os

from telegram2elastic import get_message_dict, json_default


class Writer:
    def __init__(self, config: dict):
        self.path = os.path.expanduser(config.get("path"))
        self.output_map = config.get("output_map")

    async def write_message(self, message):
        message_dict = await get_message_dict(message, self.output_map)

        with open(self.path, "a") as output_file:
            json.dump(message_dict, output_file, default=json_default)
            output_file.write("\n")
