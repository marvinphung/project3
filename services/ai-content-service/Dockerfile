FROM python:3.12-slim

WORKDIR /workspace
COPY . /workspace/services/ai-content-service
COPY packages /workspace/packages

RUN pip install --no-cache-dir uv \
    && uv pip install --system --no-cache \
       fastapi uvicorn pydantic pymongo

ENV PYTHONPATH=/workspace/services/ai-content-service/src
CMD ["python", "-m", "footballpulse_ai_content_service.server"]
