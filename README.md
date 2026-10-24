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
| Climate | Climate control: off or on, with a target temperature in your region's range. Works with thermostat cards and voice assistants |
| Switch | EV charging start/stop |
| Number | AC and DC charge limits (EVs) |
| Button | Flash hazard lights, hazard lights + horn, open/close charge port, force refresh |
| Sensor | Energy used today (with a driving / climate / electronics / battery care breakdown), lifetime energy used and regenerated, 30-day average consumption (European EVs), API requests today (on a "Bluelink account" device), odometer, range (total / fuel / EV), fuel level, EV battery %, battery health, 12V battery %, charging power, time to full, outside and set temperature, tire pressures, next service, trouble codes, last updated |
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
- **Rate limits:** see [API limits](#api-limits).

### Other regions

- **USA:** set the climate temperature in °F (62-81). The default is 70.
- **Canada:** Bluelink may email or text a one-time code during setup.
- **Everywhere else:** set the temperature in °C. The default is 21.

## API limits

Hyundai doesn't publish its limits. Owners and the community projects
built on Bluelink report **about 200 requests per day per account in
Europe**, after which every request is refused with error 5091 ("Exceeds
number of requests") until midnight. Other regions have no well-known
daily limit.

What uses requests:

| Action | Requests (Europe) |
| --- | --- |
| One normal poll (status, parked location, two energy-history requests) | 4 |
| Default polling: every 30 min, paused 22:00-07:00 | about 120 a day |
| Polling every 60 min, paused 22:00-07:00 | about 60 a day |
| A forced refresh (wakes the car) | several |
| A command (lock, climate, ...): send, up to 4 status checks 15 s apart, then a refresh | 5 to 8 |

How Moolink stays inside it:

- The **API requests today** sensor counts every request to the Bluelink
  cloud. Its attributes show the known limit and whether polling is paused.
- **Quiet hours** (22:00-07:00 by default) stop automatic polling overnight.
- Within 30 requests of the limit, automatic polling stops so the rest stay
  available for your commands.
- If Bluelink reports the limit anyway, polling pauses until midnight and
  the last known state stays on screen.

## Options

Open **Configure** on the integration to change these:

| Option | Default | Notes |
| --- | --- | --- |
| Poll interval | 30 min | Reads the state cached in the Bluelink cloud. This does not wake the car. |
| Force refresh interval | 240 min | Once cached data is older than this, the car is woken for fresh data. Each wake-up drains a little 12V battery. `0` disables it. |
| Refresh while charging | 30 min | While plugged in and charging, wake the car for fresh data this often (a charging car is awake anyway). `0` turns it off. |
| Lowest 12V battery for automatic wake-ups | 50% | Below this, the car is never woken automatically. A manual Force refresh still works. |
| Quiet hours start / end | 22:00 / 07:00 | No automatic polling in this window, so the car is never woken overnight. Commands still work. Set both to the same time to turn it off. |
| Climate temperature / duration / defrost | region default / 10 min / off | Used by the Climate control, which also changes the temperature. |
| Car's maximum temperature | empty | The highest temperature your car's climate accepts, if lower than the region allows (some Konas stop at 25 °C). Caps the Climate control and the `start_climate` action. |

## Repairs

Problems that need you appear under **Settings → Repairs** and clear
themselves once resolved:

- **Bluelink rejected the PIN**: fix it right there by entering the PIN.
- **12V battery is low**: automatic wake-ups are paused until it recovers.
- **Daily request limit reached**: polling is paused until midnight.

## Blueprints

Ready-made automations you fill in from a form. Click to import:

| Blueprint | Import |
| --- | --- |
| Car left unlocked: notify, and optionally lock it | [Import](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2FLordOfKaos%2FMoolink%2Fblob%2Fmain%2Fblueprints%2Fautomation%2Fmoolink%2Fleft_unlocked.yaml) |
| Charging finished, or battery above a level | [Import](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2FLordOfKaos%2FMoolink%2Fblob%2Fmain%2Fblueprints%2Fautomation%2Fmoolink%2Fcharging_finished.yaml) |
| Door, window, trunk or sunroof open at night | [Import](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2FLordOfKaos%2FMoolink%2Fblob%2Fmain%2Fblueprints%2Fautomation%2Fmoolink%2Fopen_at_night.yaml) |
| Pre-heat or cool at a set time on chosen days | [Import](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2FLordOfKaos%2FMoolink%2Fblob%2Fmain%2Fblueprints%2Fautomation%2Fmoolink%2Fpreheat.yaml) |

Then **Settings → Automations & scenes → Blueprints**, pick one, and fill
in the form.

## When a command fails

After each command, Moolink waits for the car to confirm and then
refreshes its state. If the car reports the command **failed** (for
example a door was open) or **timed out** (no signal, or asleep), a
notification appears in Home Assistant. A later successful command
clears it.

Every finished command also fires a `moolink_command` event with
`vehicle`, `command` and `status` (`success`, `failed` or `timeout`). To
get failures on your phone:

```yaml
automation:
  - alias: Tell me when the car ignores a command
    triggers:
      - trigger: event
        event_type: moolink_command
    conditions:
      - condition: template
        value_template: "{{ trigger.event.data.status != 'success' }}"
    actions:
      - action: notify.mobile_app_your_phone
        data:
          message: >-
            {{ trigger.event.data.vehicle }}: {{ trigger.event.data.command }}
            {{ trigger.event.data.status }}
```

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
| `CI / test` | Tests against a real Home Assistant test instance, with the Bluelink cloud mocked. Covers setup, every platform, commands, actions, the config/OTP/reauth/options flows, EU rules (PIN, °C range, UK region default), quiet hours, the request counter, command results, diagnostics redaction, repairs, energy sensors, wake-up rules, Home Assistant's own validation of every blueprint, snapshots of every entity, and a contract check that the library still has every field and region this integration uses |
| `CI / hassfest` | Home Assistant's own manifest, services and translation validator |
| `CI / hacs` | HACS repository validation |
| `Release` | After CI passes on `main`, publishes a GitHub release for a new `manifest.json` version, with notes listing every commit since the last release |
| `Weekly status` | Every Monday (and on demand): tests against the newest `hyundai_kia_connect_api`, opens an upgrade pull request when it passes, and posts a status report (library, tests, CI on `main`, latest release, open pull requests) as a comment on the **Weekly status report** issue |

Snapshots live in `tests/snapshots/`. After an intended change to an
entity, refresh them with `pytest --snapshot-update` and review the diff.

### Releasing

Bump `version` in `custom_components/moolink/manifest.json` and push to
`main`. Once CI passes, the `Release` workflow tags `v<version>` and
publishes the release, which HACS then offers as an update. Pushes that
don't change the version don't create a release.

The tests never contact Hyundai, so they need no credentials and can't
touch your car.

## Disclaimer

This project isn't affiliated with Hyundai. It uses the unofficial Bluelink
API, which can change without notice. Remote commands control a real
vehicle, so use them responsibly.
