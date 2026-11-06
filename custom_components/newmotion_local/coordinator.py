"""Polling coordinator for the NewMotion Local integration."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import (
    ChargerState,
    FinishedSession,
    NewMotionClient,
    NewMotionError,
    finished_sessions,
    meter_total_kwh,
)
from .const import (
    DOMAIN,
    EVENT_SESSION_FINISHED,
    SCAN_INTERVAL,
    SEEN_SESSIONS_KEPT,
    TRANSACTIONS_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)

type NewMotionConfigEntry = ConfigEntry[NewMotionCoordinator]

STORAGE_VERSION = 1


@dataclass(slots=True)
class NewMotionData:
    """Latest snapshot of the charger."""

    state: ChargerState
    transactions: list[dict[str, Any]] = field(default_factory=list)
    meter_total_kwh: float | None = None
    last_session: FinishedSession | None = None


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
        self._last_session: FinishedSession | None = None
        # Session ids we already announced, persisted so that a session which
        # ends while Home Assistant is down is still announced after a restart.
        self._store: Store[dict[str, Any]] = Store(
            hass, STORAGE_VERSION, f"{DOMAIN}.{entry.entry_id}.sessions"
        )
        self._seen: list[str] | None = None

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

    async def _async_process_sessions(self) -> None:
        """Announce sessions that finished since we last looked."""
        sessions = finished_sessions(self._transactions)
        if sessions:
            self._last_session = sessions[-1]

        if self._seen is None:
            stored = await self._store.async_load()
            if stored is None:
                # First run: everything already in the charger's list is history.
                self._seen = [s.session_id for s in sessions]
                await self._store.async_save({"seen": self._seen})
                return
            self._seen = list(stored.get("seen", []))

        seen = set(self._seen)
        new = [s for s in sessions if s.session_id not in seen]
        if not new:
            return

        device_id = self._device_id()
        for session in new:
            _LOGGER.debug("Session %s finished", session.session_id)
            self.hass.bus.async_fire(
                EVENT_SESSION_FINISHED,
                {
                    **session.as_event_data(),
                    "device_id": device_id,
                    "config_entry_id": self.config_entry.entry_id,
                },
            )
            self._seen.append(session.session_id)
        self._seen = self._seen[-SEEN_SESSIONS_KEPT:]
        await self._store.async_save({"seen": self._seen})

    def _device_id(self) -> str | None:
        if self.data is None:
            return None
        device = dr.async_get(self.hass).async_get_device(
            identifiers={(DOMAIN, self.data.state.charge_point_id)}
        )
        return device.id if device else None

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
                # Only the meter reading and session log depend on this.
                _LOGGER.debug("Could not read transactions: %s", err)
            else:
                self._transactions_fetched = dt_util.utcnow()
                self._last_transaction_id = state.transaction_id
                await self._async_process_sessions()

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
            last_session=self._last_session,
        )
