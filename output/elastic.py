from elasticsearch import Elasticsearch
from telethon.utils import get_display_name


class Writer:
    def __init__(self, config: dict):
        self.index_format = config.get("index_format", "telegram-%Y.%m.%d")

        username = config.get("username")
        password = config.get("password")

        if username is not None and password is not None:
            http_auth = [username, password]
        else:
            http_auth = None

        self.client = Elasticsearch(hosts=config.get("host", "localhost"), basic_auth=http_auth)

    async def write_message(self, message):
        sender_user = await message.get_sender()

        doc_data = {
            "timestamp": message.date,
            "sender": {
                "username": sender_user.username,
                "firstName": sender_user.first_name,
                "lastName": sender_user.last_name,
            },
            "chat": get_display_name(await message.get_chat()),
            "message": message.text
        }

        self.client.index(index=message.date.strftime(self.index_format), body=doc_data, id=message.id)
