FROM python:3.13-slim

ENV DEBIAN_FRONTEND=noninteractive PYTHONDONTWRITEBYTECODE=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends bash ca-certificates curl jq \
    && rm -rf /var/lib/apt/lists/*

RUN useradd -m -u 1000 -s /bin/bash agent

RUN mkdir -p /opt/desk /app/evidence /app/.desk /run/desk /logs/verifier /tests

COPY files/desk/ /opt/desk/
COPY files/deskctl.py /usr/local/bin/desk
COPY files/start-desk.sh /usr/local/bin/start-desk.sh

RUN chmod 755 /opt/desk /usr/local/bin/desk /usr/local/bin/start-desk.sh \
    && chmod 600 /opt/desk/market.db \
    && chmod 644 /opt/desk/engine.py /opt/desk/data_service.py /opt/desk/daemon.py \
       /opt/desk/manual.md /opt/desk/scenario.json \
    && chown -R root:root /opt/desk /usr/local/bin/desk /usr/local/bin/start-desk.sh \
    && chown -R agent:agent /app

WORKDIR /app

ENTRYPOINT ["/usr/local/bin/start-desk.sh"]
CMD ["sleep", "infinity"]
