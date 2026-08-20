FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /workspace

COPY packages /workspace/packages
COPY services /workspace/services

RUN pip install --no-cache-dir \
      /workspace/packages/event-contracts \
      /workspace/packages/fetch-artifacts \
      /workspace/packages/mongo-models \
      /workspace/packages/pipeline \
      /workspace/packages/runtime-config \
      /workspace/packages/shared \
      /workspace/services/article-service \
      /workspace/services/content-service \
      /workspace/services/crawler-service \
      /workspace/services/entities-extraction-service \
      /workspace/services/publisher-service \
      /workspace/services/api-gateway

COPY scripts /workspace/scripts

ENV PYTHONPATH=/workspace/packages/pipeline/src:/workspace/packages/fetch-artifacts/src:/workspace/packages/event-contracts/src:/workspace/packages/mongo-models/src:/workspace/packages/runtime-config/src:/workspace/packages/shared/src:/workspace/services/article-service/src:/workspace/services/content-service/src:/workspace/services/crawler-service/src:/workspace/services/entities-extraction-service/src:/workspace/services/publisher-service/src:/workspace/services/api-gateway/src
