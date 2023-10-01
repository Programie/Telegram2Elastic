# Changelog

## [3.1.0] - 2023-10-01

* Implemented downloading media (#3)
* Implemented translating messages (#4)

## [3.0] - 2023-03-10

* Allow to define own output map to change JSON structure sent to outputs
* Add Redis as additional output
* Each output now extends from the OutputWriter class allowing easier implementation of new output writers

## [2.1] - 2023-02-06

Fixed `AttributeError: 'NoneType' object has no attribute 'username'` in case a message was sent anonymously

## [2.0] - 2022-10-23

* Implemented support for multiple outputs
* Some refactoring of the code base

## [1.2.1] - 2022-09-19

* Added readme
* Added missing requirements.txt to be used by `pip3 install -r requirements.txt`

## [1.2] - 2022-07-01

* Fixed error "Positional arguments can't be used with Elasticsearch API methods" if using newer elasticsearch module (8.0.0)
* Replaced http_auth with basic_auth in Elasticsearch Client

## [1.1] - 2021-10-02

Chat Import: Fixed not correctly resolving entities if ID is given, prefix names with "@"

## [1.0] - 2020-10-22

Initial release