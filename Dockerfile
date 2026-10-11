
FROM python:3.11-slim

WORKDIR /app

COPY . .

RUN pip install --no-cache-dir flask gunicorn

EXPOSE 10000

CMD ["sh", "-c", "gunicorn --bind 0.0.0.0:${PORT:-10000} web_server:app"]
