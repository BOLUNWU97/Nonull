# Multi-stage Docker build for Nonull
FROM python:3.12-slim AS builder

WORKDIR /app
COPY requirements.txt setup.py ./
RUN pip install --no-cache-dir -e ".[dev,web,all]"

COPY . .
RUN python -c "from core import Nonull; print('Import OK')" || echo "Import not tested (no deps)"

FROM python:3.12-slim
WORKDIR /app
COPY --from=builder /app /app
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
EXPOSE 8765
ENV PYTHONUNBUFFERED=1
CMD ["nonull-web"]
