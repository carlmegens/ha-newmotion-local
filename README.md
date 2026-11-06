# NewMotion Local

[![Validate](https://github.com/carlmegens/ha-newmotion-local/actions/workflows/validate.yml/badge.svg)](https://github.com/carlmegens/ha-newmotion-local/actions/workflows/validate.yml)
[![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://hacs.xyz/docs/faq/custom_repositories)

Home Assistant integration that reads the **local status** of a NewMotion /
Shell Recharge **Home Advanced** charger over your own network. No cloud
account, no API key.

It is **read-only**. It only sends `GET` requests to the status server the
charger already runs on port 12800, and never changes a setting. The charger
stays connected to its OCPP back office (Shell Recharge, EVC-net, …), so
things like reimbursement of home charging costs keep working.

## Entities

| Entity | Description |
| --- | --- |
| Status | `available`, `connected` (car plugged in, not charging), `charging`, `error` |
| Car connected | A charging session is open |
| Charging | Energy is flowing to the car |
| Charging power | kW, from the charger's built-in meter |
| Charging current | A per phase |
| Active phases | 1 or 3 |
| Session energy | kWh charged in the current session |
| Session start | When the current session started |
| Total energy | Lifetime meter reading of the charger; usable in the Energy dashboard |
| Current limit | Current the charger offers right now (A per phase) |
| Maximum current | Configured maximum (diagnostic) |
| Power factor | Disabled by default |
| Back office | Whether the OCPP back office accepted the charger (diagnostic) |
| Problem | On when the charger reports errors or warnings (diagnostic) |

The status updates every 10 seconds.

## Requirements

* The charger must be on your LAN (Ethernet or Wi-Fi), not only on its
  built-in mobile modem.
* Port 12800 must answer. Check with
  `curl http://<charger-ip>:12800/user/status`, which should return JSON with
  a `cpid`. Some older units don't run this server.

Tested with a Home Advanced on firmware 1.13.1.3.

## Installation

1. In HACS (Marketplace), add this repository as a custom repository of type
   **Integration**: `https://github.com/carlmegens/ha-newmotion-local`
2. Install **NewMotion Local** and restart Home Assistant.
3. Go to **Settings → Devices & services → Add integration → NewMotion Local**
   and enter the charger's IP address. Give it a fixed address in your router.

## Use with evcc

Because the readings are local and fast, they work well as the charge meter of
an evcc loadpoint (for example through evcc's `homeassistant` meter), while
charging itself is controlled through the car.

## Development

```bash
pip install -r requirements_test.txt ruff
ruff check . && pytest
python tools/mock_newmotion.py --state charging   # fake charger on :12800
```

## Disclaimer

Not affiliated with NewMotion, Shell or EVC-net. The local status server is
not a documented API and may change with a firmware update.
