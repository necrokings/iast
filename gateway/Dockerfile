# Gateway development Dockerfile
# Builds a lightweight image to run the TN3270 gateway in local dev mode.

FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1
WORKDIR /app

# Install runtime dependencies. Pin minimal versions to match pyproject if needed.
# Install Python dependencies from pinned requirements.txt for reproducible builds
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copy application source
COPY src /app/src
COPY .env.example /app/.env.example

# Default environment variables useful for local dev
ENV REDIS_URL="redis://host.docker.internal:6379"
ENV METADATA_STORE="local"
ENV IDLE_TIMEOUT_SECS=300

# Run the gateway using the module entrypoint
CMD ["python", "-m", "src.app"]
