FROM python:3.8-buster

RUN pip install elasticsearch telethon pyyaml

COPY telegram2elastic.py /telegram2elastic.py

VOLUME /sessions

ENTRYPOINT ["/telegram2elastic.py"]