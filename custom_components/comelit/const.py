DOMAIN = "comelit"
HUB_DOMAIN = "comelit.hub"
VEDO_DOMAIN = "comelit.vedo"
CONF_MQTT_USER = "mqtt-user"
CONF_MQTT_PASSWORD = "mqtt-password"
CONF_SERIAL = "serial"
CONF_CLIENT = "client"
COVER_CLOSING_TIME = 30  # TODO config

# This fork (margiov/homeassistant-comelit) carries changes that the
# upstream maintainer (gicamm/homeassistant-comelit) has not merged - see
# https://github.com/gicamm/homeassistant-comelit/pull/132. UPSTREAM_REF is
# the last upstream commit this fork has synced its own changes on top of;
# bump it (and the date) whenever upstream is pulled in again.
UPSTREAM_REPO = "gicamm/homeassistant-comelit"
UPSTREAM_REF = "d863a43"
UPSTREAM_REF_DATE = "2026-09-15"
