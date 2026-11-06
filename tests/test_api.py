"""Tests for the status parsing."""

from __future__ import annotations

from datetime import UTC, datetime

from mock_newmotion import status_payload, transactions_payload
import pytest

from custom_components.newmotion_local.api import (
    meter_total_kwh,
    parse_charging_rate,
    parse_status,
)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Charging rate: 3.52kw 3 phase [5.11A 0.95pf ] ", (3.52, 3, 5.11, 0.95)),
        ("Charging rate: 7.4kw 1 phase [32A 1.0pf ]", (7.4, 1, 32.0, 1.0)),
        ("Charging rate: 0kw 3 phase [0A pf ] ", (0.0, 3, 0.0, None)),
        ("garbage", (None, None, None, None)),
        (None, (None, None, None, None)),
    ],
)
def test_parse_charging_rate(text, expected) -> None:
    rate = parse_charging_rate(text)
    assert (rate.power_kw, rate.phases, rate.current, rate.power_factor) == expected


def test_charging_state() -> None:
    state = parse_status(status_payload("charging"))
    assert state.charge_point_id == "07999999"
    assert state.status == "charging"
    assert state.car_connected and state.charging
    assert state.session_energy_kwh == 2.27
    assert state.session_start == datetime(2026, 11, 6, 18, 45, 4, 347000, UTC)
    assert state.current_limit == 16.0
    assert state.max_current == 16.0
    assert state.backend_connected


def test_available_state() -> None:
    state = parse_status(status_payload("available"))
    assert state.status == "available"
    assert not state.car_connected and not state.charging
    assert state.session_energy_kwh is None
    assert state.session_start is None


def test_connected_but_not_charging() -> None:
    state = parse_status(status_payload("suspended"))
    assert state.status == "connected"
    assert state.car_connected and not state.charging


def test_error_state() -> None:
    state = parse_status(status_payload("error"))
    assert state.status == "error"
    assert state.errors == ["RCD tripped"]


def test_meter_total_during_session() -> None:
    state = parse_status(status_payload("charging", consumed=2270))
    txs = transactions_payload(open_session=True)["value"]
    assert meter_total_kwh(state, txs) == 34698.44


def test_meter_total_without_session() -> None:
    state = parse_status(status_payload("available"))
    txs = transactions_payload(open_session=False)["value"]
    assert meter_total_kwh(state, txs) == 34696.17


def test_meter_total_unknown_when_session_missing_from_list() -> None:
    state = parse_status(status_payload("charging"))
    txs = transactions_payload(open_session=False)["value"]
    assert meter_total_kwh(state, txs) is None
