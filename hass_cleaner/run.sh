#!/usr/bin/with-contenv bashio
set -euo pipefail

# Remove the retired option through Supervisor, never by rewriting options.json.
if cleaner_options=$(bashio::addon.options); then
    if bashio::jq.exists "${cleaner_options}" '.deletion_mode'; then
        if bashio::addon.option 'deletion_mode'; then
            bashio::log.info "Removed obsolete deletion_mode option"
        else
            bashio::log.warning "Could not remove obsolete deletion_mode; save the app configuration and restart"
        fi
    fi
else
    bashio::log.warning "Could not inspect legacy options; continuing startup"
fi

exec python3 -m hass_cleaner
