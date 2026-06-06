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
   ```
3. Enable N3FJP's TCP API (Settings → API) on the master logging PC.
4. Run `.venv/bin/python -m openfieldday` and open `http://<pi-ip>:8000/`.

### Kiosk on the Pi
Point Chromium at the dashboard full-screen:
`chromium-browser --kiosk --app=http://localhost:8000/`

### Run as a service
Copy `deploy/openfieldday.service` to `/etc/systemd/system/`, then
`sudo systemctl enable --now openfieldday`.
