FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY ./src /app/src
COPY ./requirements.txt /app/

RUN pip3 install --no-cache-dir -r requirements.txt

RUN useradd -m vcap \
    && chown -R vcap /app

USER vcap

ENTRYPOINT ["python", "src/main.py"]