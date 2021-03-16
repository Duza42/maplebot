FROM python:3.8-slim-buster

LABEL maintainer="mjfakler"

COPY maplebot /maplebot/

RUN pip3 install --no-cache-dir --upgrade pip \
    && pip3 install --no-cache-dir -r /maplebot/requirements.txt \
    && chmod u+x /maplebot/service.sh

RUN apt-get update \
    && apt-get install -y --no-install-recommends vim \
    && rm -rf /var/lib/apt/lists/*

VOLUME /maplebot/config /maplebot/logs

ENTRYPOINT /maplebot/service.sh
