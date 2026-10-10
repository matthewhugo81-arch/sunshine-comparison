# Sunshine comparison

A static GitHub Pages dashboard comparing 24-hour sunshine at 20 UK and Irish stations.
**Experimental estimates, not verified forecasts of observed sunshine.** The October 9 audit
found impossible direct/total radiation relationships in parts of the IFS feed and limitations
in estimating sunshine duration from time-averaged radiation. Physical source failures are excluded. Unvalidated cloud/rain screens have been removed;
this does not repair the provider sunshine method. See [source findings](docs/source-assessment.md).
The date selector extends to the last complete day available from the selected model.
Compare all four models, select one, switch between station/region labels, or save a map as PNG.

## Forecaster cross-check with EPD (10–14 October 2026)

`data/epd_reference.json` contains a *limited, manually transcribed* comparison
from five user-supplied EPD probabilistic sunshine charts: the EPD central value,
10th and 90th percentiles at three clearly matched Scottish stations. It is not
the full EPD station inventory, an observation archive, or a calibration dataset;
the source forecast run and accumulation window have not been independently
checked. Any missing station/date is **unknown**, not zero.

The dashboard now shows available reference values separately. It highlights
deterministic estimates outside the displayed EPD percentile interval with a
0.5-hour allowance for whole-hour rounding, but does not reweight, suppress or
alter them. Even a large difference between two forecast systems does not by
itself establish which is more accurate.

The physical quality checks now also record **advisory** `review_flags` when
daylight-average total cloud is at least 90% while estimated sunshine exceeds
80% of astronomical daylight. Thin high cloud can coexist with sunshine: the
flag is for review, **not** a reason to withhold or change a value. Underlying
sunshine remains experimental until independently observation-validated.

## Data

ECMWF IFS, GFS, UKMO Global and UKV are requested separately from Open-Meteo's Single Runs API.
The latest common **00 UTC** cycle is used; if unavailable, the previous day's 00 UTC cycle is tried.
Hourly accumulations are summed at endpoints 01 UTC through the following 00 UTC.
All 24 sunshine hours at all 20 stations must exist before a model/day enters the dropdown.
Supporting radiation must pass physical checks at each station before its amount is displayed.
Physical failures are `null` in `daily` and shown as a gap (—); unavailable days remain absent.
Cloud and rain are optional context, never a reason to alter or suppress a sunshine amount.
Rounding is to the nearest whole hour, with halves rounded up, after summation. Provider-reported
totals remain in each day's `quality` entries, separate from the screened display values.
Maximum query windows are 15 days for IFS, 16 for GFS, 7 for UKMO Global, and 3 for UKV;
actual sunshine coverage is detected from returned data and is currently around 2 days for the UKMO feeds.

These are radiation-derived station/grid-cell estimates, not regional averages or native sunshine products.
They do not include ensemble percentiles, and have not been calibrated to ePD or verified against observations.
Open-Meteo's algorithm uses a linear 60–180 W/m² DNI ramp around the 120 W/m² threshold.
Hourly mean irradiance cannot determine how many minutes the sun was visible within an hour;
interpolation from longer model steps further limits precision. This is not the native ECMWF `sund` field.

## Quality screening

The updater validates model-specific requests, UTC timestamp continuity, station/grid distance,
units, all 24 accumulation intervals, physical ranges, and supporting data completeness.
Direct horizontal radiation must not exceed total horizontal radiation; diffuse radiation must
not be materially negative. A 2 W/m² tolerance permits rounding noise. Sunshine must fit NOAA's
apparent daylight window, allowing 2 minutes of geometry/refraction tolerance.

Sunrise and sunset use the full Gregorian date and NOAA/Meeus Julian-century equations,
iterated at each event; leap years and changes of season are automatic. Station-table daylight
uses each named station's coordinates. Quality checks use the corresponding model grid-cell
coordinates. The horizon is flat at sea level with standard refraction (90.833° zenith),
excluding twilight, terrain shading and local obstructions. Calculations stay in UTC throughout.
Daylight appears in hours and minutes; sunshine is checked before rounding to whole hours.
Thus an 11-hour display can be valid for an unrounded 10.6-hour forecast within a 10h 50m day.
Five independent US Naval Observatory reference cases cover north/south locations, summer,
winter, autumn and a leap day. Sunrise and sunset agree within one minute in those cases.

No cloud/rain thresholds suppress or reduce amounts. The former unvalidated screens
were removed on 9 October 2026. Thin cloud and showers can coexist with sunshine.
Passing the physical checks does not demonstrate forecast accuracy. Rain is not
fractionally split at sunrise/set; contextual cloud means use preceding-hour
endpoint averages weighted by daylight overlap.

The [native-source assessment](docs/source-assessment.md) records the remaining
access and definition limitations. Real GFS SUNSD records and complete Met Office
run inventories are preserved separately in `data/source-investigation-2026-10-09.json`.
Those diagnostic records are not substituted into the sunshine maps.

`data/hourly.json` retains the retrieved source fields and timestamps for reproducibility.
`data/audit-2026-10-09.json` preserves the original evidence independently of later forecast refreshes.
The regression fixture includes actual Kinloss, Bishopton and Cork data from that audit.
See the [provider algorithm](https://github.com/open-meteo/open-meteo/blob/f625df2c2b2d29d7837b1c71660fb226b1864f9b/Sources/App/Helper/Solar/SunRiseSet.swift)
and [NOAA solar geometry](https://gml.noaa.gov/grad/solcalc/calcdetails.html).
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
