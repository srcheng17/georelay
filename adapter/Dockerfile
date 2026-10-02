FROM python:3.13-slim
LABEL org.opencontainers.image.licenses="AGPL-3.0-or-later" \
      org.opencontainers.image.source="https://github.com/srcheng17/georelay"
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 ADAPTER_DB=/data/adapter.sqlite3
RUN groupadd --gid 10001 adapter && useradd --uid 10001 --gid adapter --no-create-home adapter \
    && mkdir /data && chown adapter:adapter /data
WORKDIR /app
COPY --chown=adapter:adapter __init__.py server.py ./adapter/
COPY LICENSE /usr/share/doc/georelay-adapter/LICENSE
COPY --chmod=444 MODIFICATIONS.md /usr/share/doc/georelay-adapter/MODIFICATIONS.md
USER 10001:10001
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/health', timeout=2).read()"
CMD ["python", "-m", "adapter.server"]
