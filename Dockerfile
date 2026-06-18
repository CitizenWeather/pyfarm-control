FROM python:3.11-slim-bullseye

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY . /tmp/pyfarm-control
RUN pip install --no-cache-dir /tmp/pyfarm-control \
    && rm -rf /tmp/pyfarm-control

RUN mkdir -p /var/lib/pyfarm && chmod 755 /var/lib/pyfarm

EXPOSE 8765

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8765/status', timeout=5)"

ENTRYPOINT ["pyfarm"]
CMD ["grow", "start", "/etc/pyfarm/grow.yaml", "--api-port", "8765"]
