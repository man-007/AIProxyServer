# -------------------------------------------------
# 1️⃣ Builder stage – install dependencies and compile
# -------------------------------------------------
FROM python:3.11-slim AS builder

# Install runtime dependencies (the same list you use locally)
WORKDIR /build
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# Copy the application source (the packaged layout)
COPY src/proxy_gateway ./proxy_gateway

# Compile Python to legacy side-by-side bytecode so it remains importable
# after the source files are removed from the runtime image.
RUN python -m compileall -q -b proxy_gateway

# -------------------------------------------------
# 2️⃣ Runtime stage – copy only what we need
# -------------------------------------------------
FROM python:3.11-slim

# Create a non‑privileged user (UID 10001 works well with most orchestrators)
RUN groupadd --system app && useradd --system --gid app -u 10001 --create-home app

WORKDIR /app

# Copy the installed packages from the builder stage
COPY --from=builder /install /usr/local

# Copy the compiled bytecode (keep the directory structure)
COPY --from=builder /build/proxy_gateway ./proxy_gateway
# Remove source files and cache directories, leaving only importable .pyc files.
RUN find proxy_gateway -type f -name "*.py" -delete \
    && find proxy_gateway -type d -name "__pycache__" -prune -exec rm -rf {} +

# -------------------------------------------------
# Runtime configuration
# -------------------------------------------------
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
# The proxy reads these from the environment; you can override them at `docker run` time
ENV PROXY_HOST=0.0.0.0
ENV PROXY_PORT=8080
# If you keep a .env file for secrets, mount it at runtime (see usage below)

EXPOSE 8080
USER app

# Health‑check – mirrors the one you used locally
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD ["python", "-c", \
    "import os, urllib.request; \
    req = urllib.request.Request('http://127.0.0.1:8080/health'); \
    tok = os.getenv('PROXY_API_KEY'); \
    if tok: \
    req.add_header('Authorization', 'Bearer ' + tok); \
    urllib.request.urlopen(req)"]

# Start the server
CMD ["python", "-m", "uvicorn", "proxy_gateway.main:app", "--host", "0.0.0.0", "--port", "8080"]