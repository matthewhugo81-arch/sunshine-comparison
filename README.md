# Sunshine comparison

A static GitHub Pages dashboard comparing 24-hour sunshine at 20 UK and Irish stations.
The date selector extends to the last complete day available from the selected model.
Compare all four models, select one, switch between station/region labels, or save a map as PNG.

## Data

ECMWF IFS, GFS, UKMO Global and UKV are requested separately from Open-Meteo's Single Runs API.
The latest common **00 UTC** cycle is used; if unavailable, the previous day's 00 UTC cycle is tried.
Hourly accumulations are summed at endpoints 01 UTC through the following 00 UTC.
All 24 hours at all 20 stations must exist before a model/day is published. Missing data remains missing.
Rounding is to the nearest whole hour, with halves rounded up, after summation. Unrounded totals remain in JSON.
Maximum query windows are 15 days for IFS, 16 for GFS, 7 for UKMO Global, and 3 for UKV;
actual sunshine coverage is detected from returned data and is currently around 2 days for the UKMO feeds.

These are radiation-derived station/grid-cell estimates, not regional averages or native sunshine products.
They do not include ensemble percentiles, and have not been calibrated to ePD or verified against observations.
The generic RoI row is excluded until a station or area-averaging definition is supplied.
Station-coordinate sources are recorded in `data/stations.json`; map geometry is Natural Earth 1:10m,
simplified and projected with a Lambert conformal conic projection.

## Refresh and publish

GitHub Pages must use **GitHub Actions** as its source. `.github/workflows/pages.yml` checks updates
at 02:17, 08:17, 14:17 and 20:17 UTC and on pushes/manual runs. GitHub schedules can be delayed.
Each successful refresh commits the current forecast snapshot to the repository before publishing.
Update failures stop deployment, preserving the last successful site. The browser shows a stale-data
notice when the data check is over 24 hours old or the model cycle is over 40 hours old.

No frontend credentials are required. Open-Meteo's hosted free service is for evaluation/non-commercial
use. For commercial operational use, configure the appropriate Open-Meteo subscription and add an
`OPEN_METEO_API_KEY` Actions secret; the updater uses the customer Single Runs endpoint.
Never put a private API key into the public page or data files.

Local preview and checks (Python 3.12+ and Node):

```sh
python -m unittest discover -s tests
node --check app.js
python scripts/update_forecasts.py
python -m http.server 18769 --bind 127.0.0.1
```

Sources: [ECMWF](https://open-meteo.com/en/docs/ecmwf-api),
[GFS](https://open-meteo.com/en/docs/gfs-api), [UKMO](https://open-meteo.com/en/docs/ukmo-api),
[run archive](https://open-meteo.com/en/docs/single-runs-api), [API terms](https://open-meteo.com/en/pricing).

Credit: ECMWF / NOAA / UK Met Office via Open-Meteo; map boundaries Natural Earth (public domain).
Derived forecast datasets, maps, and this project are offered under [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/).
