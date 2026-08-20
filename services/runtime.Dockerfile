FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /workspace

COPY packages /workspace/packages
COPY services /workspace/services
COPY docs/europe_top6_clubs_2026_27_aliases.json /workspace/docs/europe_top6_clubs_2026_27_aliases.json

RUN pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu "torch==2.9.1+cpu"

RUN pip install --no-cache-dir \
      /workspace/packages/event-contracts \
      /workspace/packages/fetch-artifacts \
      /workspace/packages/mongo-models \
      /workspace/packages/pipeline \
      /workspace/packages/runtime-config \
      /workspace/packages/shared \
      /workspace/services/crawler-service \
      "/workspace/services/entities-extraction-service[models]" \
      /workspace/services/content-summary-service \
      /workspace/services/publisher-service \
      /workspace/services/api-gateway

COPY scripts /workspace/scripts

ENV PYTHONPATH=/workspace/packages/pipeline/src:/workspace/packages/fetch-artifacts/src:/workspace/packages/event-contracts/src:/workspace/packages/mongo-models/src:/workspace/packages/runtime-config/src:/workspace/packages/shared/src:/workspace/services/crawler-service/src:/workspace/services/entities-extraction-service/src:/workspace/services/content-summary-service/src:/workspace/services/publisher-service/src:/workspace/services/api-gateway/src
