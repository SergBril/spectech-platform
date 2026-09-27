# ═══════════════════════════════════════════════════════════
# Multi-stage Dockerfile for SpectechPlatform Backend
# ═══════════════════════════════════════════════════════════

# ───────────────────────────────────────────────────────────
# Stage 1: Builder (compile dependencies)
# ───────────────────────────────────────────────────────────
FROM python:3.12-slim AS builder

# Установка системных шрифтов для кириллицы (ReportLab)
RUN apt-get update && \
    apt-get install -y --no-install-recommends fonts-dejavu && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /build

# Install build dependencies (fonts NOT needed for compilation)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better layer caching
COPY requirements.txt .

# Install Python dependencies in isolated prefix
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ───────────────────────────────────────────────────────────
# Stage 2: Runtime (minimal production image)
# ───────────────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

WORKDIR /app

# Install runtime dependencies + Cyrillic fonts for PDF generation
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    fonts-dejavu-core \
    fonts-dejavu-extra \
    fonts-freefont-ttf \
    fontconfig \
    libpango-1.0-0 \
    libpangoft2-1.0-0 \
    libpangocairo-1.0-0 \
    libcairo2 \
    libgdk-pixbuf-2.0-0 \
    libffi8 \
    shared-mime-info \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd -r spectech \
    && useradd -r -g spectech -d /app -s /sbin/nologin spectech

# Update font cache
RUN fc-cache -fv

# Update font cache
RUN fc-cache -fv

# Copy installed Python packages from builder
COPY --from=builder /install /usr/local

# Copy application code
COPY --chown=spectech:spectech . .

# Create necessary directories
RUN mkdir -p /app/uploads /app/logs \
    && chown -R spectech:spectech /app

# Copy entrypoint script
COPY --chown=spectech:spectech scripts/entrypoint.sh /app/scripts/entrypoint.sh
RUN chmod +x /app/scripts/entrypoint.sh

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app \
    PORT=8000

# Expose port
EXPOSE 8000

# Switch to non-root user
USER spectech

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/api/v1/system/health || exit 1

# Start application
ENTRYPOINT ["/app/scripts/entrypoint.sh"]
