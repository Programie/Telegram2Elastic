# Telegram 2 Elastic

Telegram 2 Elastic is a [Telegram](https://telegram.org) client which writes all chat messages to multiple outputs like Elasticsearch in realtime.

With the data stored in Elasticsearch, you can use applications like Kibana or Grafana to visualize the chats. Or you may use it as a much better search engine compared to the one implemented in the available Telegram clients.

## Requirements

* Python >= 3.7
* Elasticsearch (in case you want to use the Elasticsearch output)
* Telegram API ID and API Hash (create one at [my.telegram.org](https://my.telegram.org))

## Installation

* Download the latest release
* Install the required Python modules using pip: `pip3 install -r requirements.txt`
* Copy the provided config.sample.yml to config.yml and edit it to fit your needs

## Initial setup

When started for the first time, the application will ask you to connect with your Telegram account.

## Available sub commands

* `listen` - Listen for chat messages and write them to the configured outputs
* `import-history` - Import the chat history (the complete history or only for specific chats or a specific time range)
* `list-chats` - List available chats