FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app

# Oracle Instant Client 19 (o banco do Mega exige Native Network Encryption → python-oracledb em modo thick)
ARG IC_VERSAO=1927000
ARG IC_ARM=instantclient-basiclite-linux.arm64-19.27.0.0.0dbru.zip
ARG IC_X64=instantclient-basiclite-linux.x64-19.27.0.0.0dbru.zip
RUN set -e; apt-get update && apt-get install -y --no-install-recommends libaio1 unzip curl ca-certificates; \
    arq=$IC_X64; [ "$(uname -m)" = "aarch64" ] && arq=$IC_ARM; \
    curl -fsSL "https://download.oracle.com/otn_software/linux/instantclient/$IC_VERSAO/$arq" -o /tmp/ic.zip; \
    unzip -q /tmp/ic.zip -d /opt && rm /tmp/ic.zip && mv /opt/instantclient_* /opt/instantclient; \
    echo /opt/instantclient > /etc/ld.so.conf.d/oracle-instantclient.conf && ldconfig; \
    apt-get purge -y unzip curl && apt-get autoremove -y && rm -rf /var/lib/apt/lists/*
ENV MEGA_INSTANT_CLIENT=/opt/instantclient

RUN useradd --create-home --uid 10001 app
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY . .
USER app
EXPOSE 8000
# Aplica migrações e sobe a API (2 workers bastam para dezenas de usuários)
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2 --proxy-headers --forwarded-allow-ips='*'"]
