FROM alpine

ARG UV_VERSION=0.11.3

RUN apk add bash curl && \
    curl -L https://github.com/astral-sh/uv/releases/download/${UV_VERSION}/uv-x86_64-unknown-linux-musl.tar.gz | tar -C /usr/local/bin -zxp --strip-components=1

COPY output/*.py /app/output/
COPY .python-version pyproject.toml uv.lock telegram2elastic.py /app/

WORKDIR /app

RUN uv sync --no-dev

VOLUME /sessions

ENTRYPOINT ["/app/telegram2elastic.py"]
