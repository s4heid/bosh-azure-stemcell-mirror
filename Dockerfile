ARG arch=amd64
FROM --platform=linux/${arch} python:3.11-slim-buster

WORKDIR /app

COPY ./src /app/src
COPY ./requirements.txt /app/

RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

RUN pip3 install --no-cache-dir -r requirements.txt

RUN useradd -m vcap \
    && chown -R vcap /app

USER vcap

ENTRYPOINT ["python", "src/main.py"]