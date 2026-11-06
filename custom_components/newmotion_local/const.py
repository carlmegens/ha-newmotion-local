"""Constants for the NewMotion Local integration."""

from __future__ import annotations

from datetime import timedelta
from typing import Final

DOMAIN: Final = "newmotion_local"
MANUFACTURER: Final = "NewMotion"

# The charger's local status server listens on this port (Grizzly HTTP).
DEFAULT_PORT: Final = 12800

SCAN_INTERVAL: Final = timedelta(seconds=10)
# The transaction list only matters for the lifetime meter reading, which can
# be derived from the live status while a session runs. Refresh it now and then
# and whenever a session starts or ends.
TRANSACTIONS_INTERVAL: Final = timedelta(minutes=15)

REQUEST_TIMEOUT: Final = 10

# Fired on the bus for every charging session that finished.
EVENT_SESSION_FINISHED: Final = f"{DOMAIN}_session_finished"
# How many announced session ids to remember (the charger keeps about 20).
SEEN_SESSIONS_KEPT: Final = 200

# Charger status as exposed by the status sensor.
STATUS_AVAILABLE: Final = "available"
STATUS_CONNECTED: Final = "connected"
STATUS_CHARGING: Final = "charging"
STATUS_ERROR: Final = "error"
STATUS_OPTIONS: Final = [
    STATUS_AVAILABLE,
    STATUS_CONNECTED,
    STATUS_CHARGING,
    STATUS_ERROR,
]
