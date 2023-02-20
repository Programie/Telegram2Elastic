from elasticsearch import Elasticsearch

from telegram2elastic import get_message_dict


class Writer:
    def __init__(self, config: dict):
        self.index_format = config.get("index_format", "telegram-%Y.%m.%d")
        self.output_map = config.get("output_map")

        username = config.get("username")
        password = config.get("password")

        if username is not None and password is not None:
            http_auth = [username, password]
        else:
            http_auth = None

        self.client = Elasticsearch(hosts=config.get("host", "localhost"), basic_auth=http_auth)

    async def write_message(self, message):
        doc_data = await get_message_dict(message, self.output_map)

        doc_data["timestamp"] = message.date

        # get_message_dict() by default adds "id" and "date" which should not be in the body
        if "id" in doc_data:
            del doc_data["id"]
        if "date" in doc_data:
            del doc_data["date"]

        self.client.index(index=message.date.strftime(self.index_format), body=doc_data, id=message.id)
