from telegram2elastic import OutputWriter


class Writer(OutputWriter):
    def __init__(self, config: dict):
        super().__init__(config)

        elasticsearch_version = config.get("version", 8)

        match elasticsearch_version:
            case 8:
                from elasticsearch8 import Elasticsearch
            case 9:
                from elasticsearch9 import Elasticsearch
            case _:
                raise RuntimeError(f"Invalid Elasticsearch version: {elasticsearch_version}")

        self.index_format = config.get("index_format", "telegram-%Y.%m.%d")

        username = config.get("username")
        password = config.get("password")

        if username is not None and password is not None:
            http_auth = (str(username), str(password))
        else:
            http_auth = None

        self.client = Elasticsearch(hosts=config.get("host", "localhost"), basic_auth=http_auth)

    async def write_message(self, message, translated_text, downloaded_media):
        doc_data = await self.get_message_dict(message, translated_text, downloaded_media)

        doc_data["timestamp"] = message.date

        # get_message_dict() by default adds "id" and "date" which should not be in the body
        if "id" in doc_data:
            del doc_data["id"]
        if "date" in doc_data:
            del doc_data["date"]

        self.client.index(index=message.date.strftime(self.index_format), body=doc_data, id=message.id)
