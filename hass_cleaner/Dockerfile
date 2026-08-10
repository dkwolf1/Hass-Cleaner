ARG BUILD_FROM=ghcr.io/home-assistant/amd64-base-python:3.13
FROM ${BUILD_FROM}

WORKDIR /app
COPY hass_cleaner /app/hass_cleaner
COPY web /app/web
COPY run.sh /run.sh
RUN chmod a+x /run.sh

ENV PYTHONUNBUFFERED=1 \
    HASS_CLEANER_HOST=0.0.0.0 \
    HASS_CLEANER_PORT=8099 \
    HASS_CLEANER_CONFIG_ROOT=/homeassistant \
    HASS_CLEANER_DATA_ROOT=/data \
    HASS_CLEANER_AUDIT_ONLY=1

EXPOSE 8099
CMD ["/run.sh"]
