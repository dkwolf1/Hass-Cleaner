"""Single-instance setup for reference checks and Repairs."""
import voluptuous as vol
from homeassistant.config_entries import ConfigFlow


class HassCleanerConfigFlow(ConfigFlow, domain="hass_cleaner"):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        await self.async_set_unique_id("hass_cleaner_companion")
        self._abort_if_unique_id_configured()
        if user_input is not None:
            return self.async_create_entry(title="Hass-Cleaner Companion", data={})
        return self.async_show_form(step_id="user", data_schema=vol.Schema({}))
