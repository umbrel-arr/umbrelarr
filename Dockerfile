FROM python:3.13-alpine@sha256:399babc8b49529dabfd9c922f2b5eea81d611e4512e3ed250d75bd2e7683f4b0

RUN addgroup -S -g 1000 umbrelarr \
    && adduser -S -D -H -u 1000 -G umbrelarr umbrelarr \
    && mkdir -p /data \
    && chown umbrelarr:umbrelarr /data

WORKDIR /app
COPY app/app.py app/dashboard.py app/http_client.py app/reconciler.py app/state.py app/storage.py ./

ENV PORT=8080 STATE_DIR=/data
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s CMD python3 -c "from urllib.request import urlopen; urlopen('http://127.0.0.1:8080/healthz', timeout=3)"
USER umbrelarr
CMD ["python3", "/app/app.py"]
