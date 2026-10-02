# Comelit SimpleHome and Comelit Vedo integration for Home Assistant

[![CI actions](https://img.shields.io/github/actions/workflow/status/margiov/homeassistant-comelit/ci.yml?branch=master&style=flat-square&label=CI)](https://github.com/margiov/homeassistant-comelit/actions/workflows/ci.yml)
[![GitHub Release](https://img.shields.io/github/v/tag/margiov/homeassistant-comelit.svg?style=flat-square)](https://github.com/margiov/homeassistant-comelit/releases)
[![GitHub commit activity](https://img.shields.io/github/commit-activity/y/margiov/homeassistant-comelit.svg?style=flat-square)](https://github.com/margiov/homeassistant-comelit/commits)
[![License](https://img.shields.io/github/license/margiov/homeassistant-comelit.svg?style=flat-square)](LICENSE)
[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=margiov&repository=homeassistant-comelit&category=integration)

Comelit SimpleHome and Comelit Vedo integration lets you connect your Home Assistant instance to Comelit Simple Home and
Vedo
systems.

For more information, see the [Wiki](https://github.com/gicamm/homeassistant-comelit/wiki) of the upstream project (general configuration is the same; see "Fork status" below for what is different here).

### Fork status

This is a maintained fork of [gicamm/homeassistant-comelit](https://github.com/gicamm/homeassistant-comelit), kept as
an independent HACS repository because the upstream maintainer has not merged the changes below:

- Support for the Comelit Vedo app firmware v1.0.1 / VEDOIPA module (login fix, arm/disarm via POST, area
  visibility filtering, ARMING/TRIGGERED states) -
  [upstream PR #132](https://github.com/gicamm/homeassistant-comelit/pull/132), left open but not accepted since it
  would require the older VEDOIP module to keep working too, which nobody has been able to test against.
- HVAC cool mode support for the climate entity.
- More robust Vedo login/session handling (the panel can answer `200 OK` with a cookie even when the login was
  rejected; this is now detected instead of surfacing as a generic JSON parsing error).

This fork tracks upstream `master` and pulls in new upstream commits regularly; it is synced up to
[`gicamm/homeassistant-comelit@d863a43`](https://github.com/gicamm/homeassistant-comelit/commit/d863a43adecb4224785c9fc1072dfeefd77c7941)
(2026-09-15) plus the changes above. The integration logs this same information (version + upstream sync point) once
at startup.

### Installation

- Install
  using [HACS](https://my.home-assistant.io/redirect/hacs_repository/?owner=margiov&repository=homeassistant-comelit&category=integration) (
  Or copy the contents of `custom_components/comelit/` to `<your config dir>/custom_components/comelit/`.)
- Add the following to your `<your config dir>/configuration.yaml` file:

```yaml
# Comelit Hub/Vedo
comelit:
  hub:
    host: HUB IP ADDRES
    port: 1883
    mqtt-user: hsrv-user
    mqtt-password: sf1nE9bjPc
    username: 'HUB USER'
    password: 'HUB PASSWORD'
    serial: HUB SERIAL
    client: homeassistant
    scan_interval: 2
  vedo:
    host: VEDO IP ADDRESS
    port: 80
    password: 'VEDO PASSWORD'
    scan_interval: 30

```

- Restart Home Assistant

### How to find the hub serial?

#### Comelit app

- Open the Comelit app
- Scan for a new hub device (Or if it's already added to the app, check in 'Manage Devices' -> Comelit Hub -> Network Configuration -> ID)
- Copy the serial (Hub MAC Address) (remove all symbols and hsrv prefix, i.e. "HSRV 00:25:29:17:2D:C2" -> "002529172DC2")

For more information, see the [Wiki](https://github.com/gicamm/homeassistant-comelit/wiki).

### Supported features
- Lights
- Shutters
- Energy Production
- Energy Consumption
- Clima
- Temperature/Humidity
- Automation
- Scenario
- Alarm

The integration also exports the alarm sensor as a presence detector. It allows presence-based lights, scenes, and so
on.

#### Comelit scenario

The integration supports the comelit scenario. It exports the scenario as a scene. A scene can be useful for exporting
some VIP features (such as opening the door) which, otherwise, cannot be fully reachable through the Hub.

### Lovelace example

Below is an example with lovelace:

```yaml
- type: entities
  title: Test
  entities:

# lights
  - entity: light.comelit_light_garage
    name: Garage
  - entity: light.comelit_light_bathroom
    name: Bathroom

# power
  - entity: sensor.comelit_power_prod_ftv
    name: Production
  - entity: sensor.comelit_power_cons
    name: Consume

    # door lock
  - entity: scene.comelit_doorlock
    name: Door lock
    icon: mdi:key

    # switch
  - entity: switch.comelit_switch1
    name: Switch1

    # clima
  - entity: climate.comelit_bathroom
    name: Bathroom
  - entity: climate.comelit_living
    name: Living

    # humidity
  - entity: sensor.comelit_humidity_bathroom
    name: Bathroom
  - entity: sensor.comelit_humidity_living
    name: Living

    # temperature
  - entity: sensor.comelit_temperature_bathroom
    name: Bathroom
  - entity: sensor.comelit_temperature_living
    name: Living

    # shutters
  - entity: cover.comelit_living
    name: Living
  - entity: cover.comelit_kitchen_sx
    name: Kitchen

    # vedo Alarm
  - entity: binary_sensor.comelit_vedo_garage
    name: Garage
  - entity: alarm_control_panel.comelit_vedo_garage
    name: Garage

```

### Development

All development tooling (dependency groups, ruff, pytest and coverage) is
configured in `pyproject.toml`. Home Assistant itself is only a test
dependency; the integration's runtime requirements live in
`custom_components/comelit/manifest.json`.

This repository is **not** a pip-installable package: `pip install .` will not
work and is not meant to. Install the development dependency groups instead.

Home Assistant 2025.4.x needs Python 3.13 (its dependencies have no wheels for
3.14 yet), so pin the interpreter when creating the virtualenv:

```bash
python3.13 -m venv venv                # or: uv venv --python 3.13 venv
source venv/bin/activate
python3 -m pip install --upgrade pip   # `--group` needs pip >= 25.1
python3 -m pip install --group dev     # or --group lint / --group test

ruff check .    # lint
pytest          # tests + coverage (writes coverage.xml)
```
