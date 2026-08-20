FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /workspace

COPY . /workspace/services/entities-extraction-service

RUN pip install --no-cache-dir /workspace/services/entities-extraction-service

ENV PYTHONPATH=/workspace/services/entities-extraction-service/src
CMD ["python", "-m", "footballpulse_entities_extraction_service.server"]
