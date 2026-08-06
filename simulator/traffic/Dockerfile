FROM python:3.12-slim-bookworm

WORKDIR /app

RUN pip install --no-cache-dir httpx==0.28.1

COPY simulator/traffic/generator.py /app/generator.py

ENV SIM_URL=http://demo-service:8080 \
    TRAFFIC_RPS=5

CMD ["python", "/app/generator.py"]
