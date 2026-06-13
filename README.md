# OpenFieldDay

Self-hosted alternative to the N3FJP software. Run on a Raspberry Pi connected to a TV.


## Running

1. `python -m venv .venv && .venv/bin/pip install -e ".[dev]"`
2. Set N3FJP host/port in `config.yaml` (or copy from defaults; the settings page
   manages power class and bonuses). Example:
   ```yaml
   n3fjp_host: 192.168.1.50
   n3fjp_port: 1100
   power_multiplier: 2
   bonuses: {}
   # Optional: override any of the dashboard theme colors (others keep defaults).
   colors:
     accent: "#ffd166"
     bg: "#0b1021"
   # Optional: absolute path to a logo image. The logo tile only appears when this
   # points at a readable file; the dashboard serves it from /logo.
   logo_path: /home/pi/field-day-logo.png
   ```
   Theme keys: `bg`, `panel`, `fg`, `accent`, `bad`, `good`.
3. Enable N3FJP's TCP API (Settings → API) on the master logging PC.
4. Run `.venv/bin/python -m openfieldday` and open `http://<pi-ip>:8000/`.

### Kiosk on the Pi
Point Chromium at the dashboard full-screen:
`chromium-browser --kiosk --app=http://localhost:8000/`

### Run as a service
Copy `deploy/openfieldday.service` to `/etc/systemd/system/`, then
`sudo systemctl enable --now openfieldday`.

### Known limitations
- Deleting QSOs in N3FJP is reflected on the scoreboard, **except** deleting the
  log down to zero contacts: to guard against a malformed read wiping the board,
  an empty list is ignored, so a fully-cleared log needs an app restart to show 0.
