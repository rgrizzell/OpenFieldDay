# OpenFieldDay

Self-hosted alternative to the N3FJP software. Run on a Raspberry Pi connected to a TV.


## Running

1. `python -m venv .venv && .venv/bin/pip install -e ".[dev]"`
2. Create `config.yaml` with the N3FJP target (or rely on the defaults below).
   Power class, bonuses, and the N3FJP host/port are also editable from the
   in-app settings page (the cog icon); changing the host/port there re-points
   the live connection without a restart, so DHCP address changes are easy to
   follow. Example:
   ```yaml
   n3fjp_host: 192.168.1.50
   n3fjp_port: 1100
   power_multiplier: 2
   bonuses: {}
   ```
   See [Theme and logo](#theme-and-logo) below for the optional `colors`,
   `logo_path`, and auto-mode window settings.
3. Enable N3FJP's TCP API (Settings → API) on the master logging PC.
4. Run `.venv/bin/python -m openfieldday` and open `http://<pi-ip>:8000/`.

### Kiosk on the Pi
Point Chromium at the dashboard full-screen:
`chromium-browser --kiosk --app=http://localhost:8000/`

### Run as a service
Copy `deploy/openfieldday.service` to `/etc/systemd/system/`, then
`sudo systemctl enable --now openfieldday`.

## Theme and logo

### Theme

The dashboard ships with built-in Solarized **light** and **dark** palettes. The
icon button in the header cycles through four modes; the choice is remembered per
browser and shared between the dashboard and the settings page:

| Mode | Behavior |
| --- | --- |
| **Auto** (clock icon) | Light during the configured daytime window, dark otherwise. |
| **System** (monitor icon) | Follows the browser/OS light-or-dark preference. |
| **Light** / **Dark** (sun / moon) | Fixed; disables automatic switching. |

Configure the "auto" daytime window in `config.yaml` with 24-hour **local** hours
(defaults are light from 05:00 to 21:00):

```yaml
auto_light_start: 5    # light mode begins at 05:00 local
auto_light_end: 21     # dark mode begins at 21:00 local
```

The easiest way to make a theme from your logo is the **Theme Builder** (Settings →
Theme builder, or `/builder.html`). Pick six colors per mode — background, panel,
text, accent, and the good/bad status colors — with a live preview, then Save. The
app derives borders, muted text, tile fill, and guaranteed-readable text-on-color
automatically, so any palette stays legible.

The builder writes the six base colors per mode into `config.yaml`:

```yaml
colors:
  light:
    bg: "#F4F1E9"      # Cream — page background
    panel: "#E7E8E2"   # Bone — tile background
    fg: "#1A1A1A"      # Ink — text
    accent: "#0032CB"  # Cobalt
    good: "#2E7D32"    # status: connected / worked
    bad: "#D90000"     # status: disconnected (Race Red)
  dark:
    bg: "#0A1A3F"      # Midnight
    panel: "#11254F"
    fg: "#E7E8E2"
    accent: "#5A9CF2"  # Sky Blue
    good: "#43A047"
    bad: "#D90000"
```

(The example above is the bundled RARA palette.) Advanced users can still pin any
derived variable — `panel`, `line`, `dim`, `tile-bg`, `on-accent`, `on-good`,
`on-bad` — by adding it alongside the six base colors; an explicit value wins over
the derived one.

### Logo

Point `logo_path` at an absolute path to a readable image (PNG or SVG):

```yaml
logo_path: /home/pi/field-day-logo.png
```

The logo tile appears on the top row **only** when the file exists and is
readable — leave `logo_path` unset (or pointing nowhere) to hide it entirely. The
dashboard serves the image from `/logo` and cache-busts it on each load, so
swapping the file shows up after a refresh without renaming it.

## Known limitations
- Deleting QSOs in N3FJP is reflected on the scoreboard, **except** deleting the
  log down to zero contacts: to guard against a malformed read wiping the board,
  an empty list is ignored, so a fully-cleared log needs an app restart to show 0.
