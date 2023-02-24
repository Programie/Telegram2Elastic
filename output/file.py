import json
import os

from telegram2elastic import json_default, OutputWriter


class Writer(OutputWriter):
    def __init__(self, config: dict):
        super().__init__(config)

        self.path = os.path.expanduser(config.get("path"))

    async def write_message(self, message):
        message_dict = await self.get_message_dict(message)

        with open(self.path, "a") as output_file:
            json.dump(message_dict, output_file, default=json_default)
            output_file.write("\n")
