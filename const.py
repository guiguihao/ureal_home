"""Constants for the ureal_home integration."""

DOMAIN = "ureal_home"

# Config entry keys
CONF_TOKEN = "token"
CONF_APP_KEY = "app_key"
CONF_SN = "sn"
CONF_API_URL = "api_url"

# Default values
DEFAULT_API_URL = "https://app-user.hzureal.com"
DEFAULT_SCAN_INTERVAL = 30  # seconds

# Platforms to load
PLATFORMS = ["sensor", "switch"]

# Device type identifiers (match values returned by your cloud API)
DEVICE_TYPE_SENSOR = "sensor"
DEVICE_TYPE_SWITCH = "switch"
DEVICE_TYPE_LIGHT = "light"

# hass.data keys
DATA_COORDINATOR = "coordinator"
DATA_API = "api"
