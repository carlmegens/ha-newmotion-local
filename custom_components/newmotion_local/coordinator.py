"""Polling coordinator for the NewMotion Local integration."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import (
    ChargerState,
    NewMotionClient,
    NewMotionError,
    meter_total_kwh,
)
from .const import DOMAIN, SCAN_INTERVAL, TRANSACTIONS_INTERVAL

_LOGGER = logging.getLogger(__name__)

type NewMotionConfigEntry = ConfigEntry[NewMotionCoordinator]


@dataclass(slots=True)
class NewMotionData:
    """Latest snapshot of the charger."""

    state: ChargerState
    transactions: list[dict[str, Any]] = field(default_factory=list)
    meter_total_kwh: float | None = None


class NewMotionCoordinator(DataUpdateCoordinator[NewMotionData]):
    """Poll the status; refresh the session list now and then."""

    config_entry: NewMotionConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: NewMotionConfigEntry,
        client: NewMotionClient,
    ) -> None:
        """Initialise the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN} {client.host}",
            update_interval=SCAN_INTERVAL,
        )
        self.client = client
        self._transactions: list[dict[str, Any]] = []
        self._transactions_fetched: datetime | None = None
        self._last_transaction_id: Any = None
        self._meter_total: float | None = None

    def _transactions_stale(self, state: ChargerState) -> bool:
        if self._transactions_fetched is None:
            return True
        if state.transaction_id != self._last_transaction_id:
            return True  # a session started or ended
        if (
            state.transaction is not None
            and state.transaction_id is not None
            and not any(
                tx.get("privateID") == state.transaction_id for tx in self._transactions
            )
        ):
            return True  # the open session is not in our list yet
        return dt_util.utcnow() - self._transactions_fetched >= TRANSACTIONS_INTERVAL

    async def _async_update_data(self) -> NewMotionData:
        """Fetch the latest state from the charger."""
        try:
            state = await self.client.get_status()
        except NewMotionError as err:
            raise UpdateFailed(f"Cannot read {self.client.host}: {err}") from err

        if self._transactions_stale(state):
            try:
                self._transactions = await self.client.get_transactions()
            except NewMotionError as err:
                # Only the lifetime meter reading depends on this; keep going.
                _LOGGER.debug("Could not read transactions: %s", err)
            else:
                self._transactions_fetched = dt_util.utcnow()
                self._last_transaction_id = state.transaction_id

        total = meter_total_kwh(state, self._transactions)
        # The meter only goes up. Ignore a reading that would go backwards
        # (e.g. a session list that lags behind the live status).
        if total is not None and (
            self._meter_total is None or total >= self._meter_total
        ):
            self._meter_total = total

        return NewMotionData(
            state=state,
            transactions=self._transactions,
            meter_total_kwh=self._meter_total,
        )
