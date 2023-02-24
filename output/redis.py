import json

from redis import Redis

from telegram2elastic import get_message_dict, json_default


class Writer:
    def __init__(self, config: dict):
        self.output_map = config.get("output_map")
        self.key = config.get("key")

        self.client = Redis(host=config.get("host", "localhost"), port=config.get("port", 6379), db=config.get("db", 0), username=config.get("username"), password=config.get("password"))

    async def write_message(self, message):
        message_dict = await get_message_dict(message, self.output_map)

        self.client.rpush(self.key, json.dumps(message_dict, default=json_default))
