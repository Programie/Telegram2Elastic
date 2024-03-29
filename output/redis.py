import json

from redis import Redis

from telegram2elastic import json_default, OutputWriter


class Writer(OutputWriter):
    def __init__(self, config: dict):
        super().__init__(config)

        self.key = config.get("key")

        self.client = Redis(host=config.get("host", "localhost"), port=config.get("port", 6379), db=config.get("db", 0), username=config.get("username"), password=config.get("password"))

    async def write_message(self, message, translated_text, downloaded_media):
        message_dict = await self.get_message_dict(message, translated_text, downloaded_media)

        self.client.rpush(self.key, json.dumps(message_dict, default=json_default))
