# Telegram 2 Elastic

Telegram 2 Elastic is a [Telegram](https://telegram.org) client which writes all chat messages to multiple outputs like Elasticsearch in realtime.

With the data stored in Elasticsearch, you can use applications like Kibana or Grafana to visualize the chats. Or you may use it as a much better search engine compared to the one implemented in the available Telegram clients.

[![DockerHub](https://img.shields.io/badge/download-DockerHub-blue?logo=docker)](https://hub.docker.com/r/programie/telegram2elastic)
[![GitHub release](https://img.shields.io/github/v/release/Programie/Telegram2Elastic)](https://github.com/Programie/Telegram2Elastic/releases/latest)

## Requirements

* Python >= 3.7
* Elasticsearch (in case you want to use the Elasticsearch output)
* Redis (in case you want to use the Redis output)
* Telegram API ID and API Hash (create one at [my.telegram.org](https://my.telegram.org))

## Installation

* Download the latest release
* Install the required Python modules using pip: `pip3 install -r requirements.txt`
* Copy the provided config.sample.yml to config.yml and edit it to fit your needs

## Outputs

It is supported to write to multiple outputs. You may pick any combination of the following output types:

* `elasticsearch`: Write to an Elasticsearch instance
* `file`: Write a line in JSON format for each message into a file
* `redis`: Append messages encoded as JSON to a list in Redis
* `tcp`: Send messages as JSON strings to any TCP socket

It is also possible to configure the same output type multiple times but using different endpoints.

### Customize output map

For each output, it is possible to customize the output map which is written to the output.

The output map can be specified using the `output_map` config property of the output.

Each property of the map defines a piece of Python code which should be executed to get the value for each field.

By default, the following map is used:

```yaml
id: "message.id"
date: "message.date"
sender: "sender"
chat: "get_display_name(await message.get_chat())"
message: "message.text"
```

## Media downloads

It is not only possible to store the text messages in something like Elasticsearch. There is also the possibility to download media files attached to those messages.

To enable that, you simply add the following configuration to your `config.yml`:

```yaml
media:
  download_path: /path/where/to/put/media-files
```

There are also some more options to restrict those downloads to specific file types, chats or limit them by size. For more options, have a look into the [config.sample.yml](config.sample.yml).

## Translate messages

It is possible to use the Telegram API to translate messages.

You might specify the target language using the `translate_to_lang` property in your `config.yml`:

```yaml
translate_to_lang: "en"
```

Note: Use the two-letter ISO 639-1 language code (examples: "de", "en", "es", "it").

The translated message will be written into `translated_text` which can be mapped to any field using the output map configuration in your `config.yml`:

```yaml
output_map:
  "message.original": "message.text"
  "message.translated": "translated_text"
```

## Initial setup

When started for the first time, the application will ask you to connect with your Telegram account.

## Available sub commands

* `listen` - Listen for chat messages and write them to the configured outputs
* `import-history` - Import the chat history (the complete history or only for specific chats or a specific time range)
* `list-chats` - List available chats