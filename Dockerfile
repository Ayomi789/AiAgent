# Sentinel dashboard + scan agent, production image.
#
# Build context is the repo root (see compose.yaml). The Python package
# lives in agent/ (agent/src/qaagent); the WSGI entrypoint is ./wsgi.py.
#
# Playwright base image so browser + OS deps are present - the hard part
# of containerizing browser automation. The image version pins the browser
# build; the matching Python client version must stay in lockstep.
FROM mcr.microsoft.com/playwright/python:v1.49.0-jammy

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    # No system Edge in Linux containers - use Playwright's Chromium.
    BROWSER_CHANNEL=chromium \
    # State root (reports/, users.db, tokens). Mount a volume here.
    SENTINEL_DATA_DIR=/data \
    # Dashboard-created site configs persist next to the state.
    SENTINEL_CONFIG_DIR=/data/configs

WORKDIR /app

# Install the package (agent/pyproject.toml) with production extras, then
# the browser build matching the base image's Playwright version.
COPY agent/pyproject.toml agent/README.md /app/agent/
COPY agent/src /app/agent/src
COPY wsgi.py /app/wsgi.py
RUN cd /app/agent \
    && pip install --no-cache-dir -e ".[prod,targets]" \
    && playwright install chromium

# Runtime state (reports/, users.db, tokens, configs) - mount a volume at /data.
RUN mkdir -p /data/reports /data/configs \
    && chown -R pwuser:pwuser /data /app

# Non-root user provided by the Playwright base image.
USER pwuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=4)"

# WSGI entrypoint (see wsgi.py). gunicorn is Unix-only - by design, this
# image is the production target; local dev uses `sentinel dashboard`.
CMD ["gunicorn", "--workers", "2", "--threads", "4", "--timeout", "600", \
     "--access-logfile", "-", "--bind", "0.0.0.0:8000", "wsgi:app"]
