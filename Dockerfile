# Nonull AI Agent — Multi-stage Docker Build
# ============================================

# Stage 1: Builder
FROM python:3.12-slim AS builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy project files
COPY pyproject.toml .
COPY core/ core/
COPY memory/ memory/
COPY safety/ safety/
COPY skills/ skills/
COPY domains/ domains/
COPY orchestration/ orchestration/
COPY channels/ channels/
COPY hooks/ hooks/
COPY persona/ persona/
COPY config/ config/
COPY evaluation/ evaluation/
COPY i18n/ i18n/
COPY experimental/ experimental/
COPY nonull/ nonull/
COPY AGENT.md CLAUDE.md README.md CHANGELOG.md .

# Install package (with dev deps)
RUN pip install --no-cache-dir --prefix=/install .[dev]

# Stage 2: Runtime
FROM python:3.12-slim

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /install /usr/local
COPY --from=builder /app .

# Create non-root user
RUN groupadd -r nonull 2>/dev/null || true
RUN useradd -r -g nonull -d /app -s /sbin/nologin nonull 2>/dev/null || true
RUN chown -R nonull:nonull /app 2>/dev/null || true

USER nonull

# Expose ports
EXPOSE 8765

# Healthcheck
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "from core.llm_client import LLMConfig; print('healthy')" || exit 1

# Default command
CMD ["python", "-m", "nonull"]
