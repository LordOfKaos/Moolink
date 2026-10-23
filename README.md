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

### HACS (recommended)

1. In HACS, open the menu and choose **Custom repositories**.
2. Add `https://github.com/lordofkaos/moolink` with type **Integration**.
3. Install **Moolink (Hyundai Bluelink)** and restart Home Assistant.

### Manual

Copy `custom_components/moolink` into your Home Assistant
`config/custom_components/` folder and restart.

## Setup

**Settings → Devices & services → Add integration → Moolink**, then enter:

- **Email / Password:** your Bluelink app login.
- **PIN:** your 4-digit Bluelink PIN. Most regions need it for remote commands.
- **Region / Brand:** where your account is registered. The default is USA / Hyundai.

If Bluelink asks to verify a new device (Canada does this), you'll be asked
where to send a one-time code and then to enter it. The session token is
saved, so restarting Home Assistant doesn't trigger another code.

### Region notes

- **USA:** set the climate temperature in °F. The default is 70.
- **Canada, Europe, Australia, and others:** set the temperature in °C. The default is 21.
- **Europe:** Hyundai's EU login now uses a captcha. If your normal password is
  rejected, enter a Bluelink *refresh token* in the password field instead.
  The `hyundai_kia_connect_api` project documents how to get one. Newer EU
  accounts may need the **Europe (CCI/GSPA)** region.

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
        below: 40
    actions:
      - action: moolink.start_climate
        data:
          device_id: YOUR_DEVICE_ID
          temperature: 72
          defrost: true
          duration: 15
```

## Development

```bash
python -m venv .venv && . .venv/bin/activate
pip install -r requirements_test.txt
pytest
```

## Disclaimer

This project isn't affiliated with Hyundai. It uses the unofficial Bluelink
API, which can change without notice. Remote commands control a real
vehicle, so use them responsibly.
