import json
import os

from telegram2elastic import get_message_dict


class Writer:
    def __init__(self, config: dict):
        self.path = os.path.expanduser(config.get("path"))

    async def write_message(self, message):
        message_dict = await get_message_dict(message)

        message_dict["date"] = message_dict["date"].isoformat()

        with open(self.path, "a") as output_file:
            json.dump(message_dict, output_file)
            output_file.write("\n")
