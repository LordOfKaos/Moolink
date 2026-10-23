# Moolink: Hyundai Bluelink for Home Assistant

A custom Home Assistant integration that lets you track and control a Hyundai
(and Genesis or Kia) vehicle through the Bluelink cloud. It's built on
[`hyundai_kia_connect_api`](https://github.com/Hyundai-Kia-Connect/hyundai_kia_connect_api),
the same client library the community `kia_uvo` integration uses, so login
and region quirks are handled by a maintained library.

## What you get

Entities are only created for values your car actually reports and commands
your region's API supports.

| Platform | Entities |
| --- | --- |
| Device tracker | GPS location |
| Lock | Door lock / unlock |
| Switch | Climate (remote start with your default settings), EV charging start/stop |
| Number | AC and DC charge limits (EVs) |
| Button | Flash hazard lights, hazard lights + horn, open/close charge port, force refresh |
| Sensor | Odometer, range (total / fuel / EV), fuel level, EV battery %, battery health, 12V battery %, charging power, time to full, outside and set temperature, tire pressures, next service, trouble codes, last updated |
| Binary sensor | Engine running, each door / window / trunk / hood / sunroof, charging, plugged in, charge port, defrost and heaters, low fuel, tire pressure and fluid / key fob / 12V warnings |

### Actions

- `moolink.start_climate`: start climate with specific temperature, duration,
  defrost, heated accessories and seat levels.
- `moolink.force_refresh`: wake the car and fetch fresh data (one car or all).
- `moolink.set_charge_limits`: set the AC and DC targets together.

## Installation

### HACS

HACS can only install from **public** repositories. If this repo is private,
use the manual install below, or make the repo public first.

1. In HACS, open the menu and choose **Custom repositories**.
2. Add `https://github.com/lordofkaos/moolink` with type **Integration**.
3. Install **Moolink (Hyundai Bluelink)** and restart Home Assistant.

### Manual

Copy `custom_components/moolink` into your Home Assistant
`config/custom_components/` folder and restart.

The integration ships its own icon (`brand/icon.png`), which Home Assistant
2026.3 and newer show automatically.

## Setup

**Settings → Devices & services → Add integration → Moolink**, then enter:

- **Email / Password:** your Bluelink app login.
- **PIN:** your 4-digit Bluelink PIN. Most regions need it for remote commands.
- **Region / Brand:** where your account is registered. The default is USA / Hyundai.

If Bluelink asks to verify a new device (Canada does this), you'll be asked
where to send a one-time code and then to enter it. The session token is
saved, so restarting Home Assistant doesn't trigger another code.

### UK and Europe

- **Region:** choose **Europe**. It's suggested automatically when Home
  Assistant's country is set to the UK or another European country. It
  covers both older cars and newer ones (for example the 2024+ IONIQ 5,
  Kona and Santa Fe). If login or data fails, try **Europe (new Bluelink app
  backend)**, which uses the same servers as the current Bluelink Europe app.
- **Password:** your normal Bluelink password works.
- **PIN:** required. The EU API checks it on every remote command. A wrong
  PIN shows up as "PIN verification failed" when you send a command.
- **Temperature:** in °C, from 14 to 31.5 in 0.5 steps. The default is 21.
  Values outside that range are rejected before anything is sent to the car.
- **Units:** the Bluelink cloud can report distances in km even for UK
  cars, and Home Assistant also converts them to its own unit system. To
  see miles, open each distance sensor's settings and set **Unit of
  measurement** to `mi`. Tire pressures use the car's own display unit.
- **Rate limits:** Hyundai Europe caps the number of API calls per day. The
  defaults (30-minute polling, a wake-up every 4 hours) stay well within it.
  Very short poll intervals or frequent force refreshes can lock you out
  until the next day.

### Other regions

- **USA:** set the climate temperature in °F (62-81). The default is 70.
- **Canada:** Bluelink may email or text a one-time code during setup.
- **Everywhere else:** set the temperature in °C. The default is 21.

## Options

Open **Configure** on the integration to change these:

| Option | Default | Notes |
| --- | --- | --- |
| Poll interval | 30 min | Reads the state cached in the Bluelink cloud. This does not wake the car. |
| Force refresh interval | 240 min | Once cached data is older than this, the car is woken for fresh data. Each wake-up drains a little 12V battery. `0` disables it. |
| Climate temperature / duration / defrost | region default / 10 min / off | Used by the Climate switch. |

After each command, the integration waits for the car to confirm and then
refreshes its state.

## Example automation

```yaml
automation:
  - alias: Pre-heat the car on cold weekday mornings
    triggers:
      - trigger: time
        at: "07:15:00"
    conditions:
      - condition: time
        weekday: [mon, tue, wed, thu, fri]
      - condition: numeric_state
        entity_id: sensor.ioniq_5_outside_temperature
        below: 5
    actions:
      - action: moolink.start_climate
        data:
          device_id: YOUR_DEVICE_ID
          temperature: 21
          defrost: true
          duration: 15
```

## Development

```bash
python3.13 -m venv .venv && . .venv/bin/activate
pip install -r requirements_test.txt
pytest --cov          # tests + coverage (fails under 85%)
ruff check . && ruff format --check .
```

### Automated testing

GitHub Actions run on every push:

| Workflow | What it checks |
| --- | --- |
| `CI / lint` | `ruff` lint and formatting |
| `CI / test` | Tests against a real Home Assistant test instance, with the Bluelink cloud mocked. Covers setup, every platform, commands, actions, the config/OTP/reauth/options flows, EU rules (PIN, °C range, UK region default), and a contract check that the library still has every field and region this integration uses |
| `CI / hassfest` | Home Assistant's own manifest, services and translation validator |
| `CI / hacs` | HACS repository validation |
| `Bluelink library compatibility` | Weekly (and on demand): reruns the tests against the newest `hyundai_kia_connect_api`, so an upstream change that breaks this integration is caught before you bump the version |

The tests never contact Hyundai, so they need no credentials and can't
touch your car.

## Disclaimer

This project isn't affiliated with Hyundai. It uses the unofficial Bluelink
API, which can change without notice. Remote commands control a real
vehicle, so use them responsibly.
