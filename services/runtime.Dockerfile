FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /workspace

COPY packages /workspace/packages
COPY services /workspace/services

RUN pip install --no-cache-dir \
      /workspace/packages/event-contracts \
      /workspace/packages/fetch-artifacts \
      /workspace/services/article-service \
      /workspace/services/content-service \
      /workspace/services/crawler-service \
      /workspace/services/intelligence-service \
      /workspace/services/api-gateway \
      /workspace/services/ai-content-service

COPY scripts /workspace/scripts

ENV PYTHONPATH=/workspace/services/crawler-service/src:/workspace/services/article-service/src:/workspace/packages/fetch-artifacts/src:/workspace/packages/event-contracts/src
