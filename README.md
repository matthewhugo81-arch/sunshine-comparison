# Sunshine comparison

A static GitHub Pages dashboard comparing 24-hour sunshine and daylight cloud at 20 UK and Irish stations.
**Experimental estimates, not verified forecasts of observed sunshine.** The October 9 audit
found impossible direct/total radiation relationships in parts of the IFS feed and limitations
in estimating sunshine duration from time-averaged radiation. Physical source failures are excluded.
Unvalidated cloud/rain suppression rules have been removed; this does not repair the provider
sunshine method. See [source findings](docs/source-assessment.md).
Compare all four models, select one, switch between station/region labels, or save a map as PNG.
The date selector follows complete sunshine or cloud data; cloud-only dates are explicitly labelled.

## All-model cloud analysis

**Total, low, medium and high cloud are all used** for ECMWF IFS, GFS, UKMO Global
and UKV. Each model retains its own cloud, sunshine, radiation, run and sampled
grid point. Provider total cloud is not reconstructed by adding overlapping layers.
The station-selectable cloud table compares all four fields beside sunshine;
the all-station quality table and map/number tooltips expose the same context.

Cloud means are time-weighted over sunrise to sunset, not averaged over 24 hours.
Hourly instantaneous cloud amounts are linearly interpolated and integrated only
across the daylight portion of each hour, including partial sunrise/set hours.
This is a sampling approximation, not observed sub-hourly cloud evolution.

Each field requires complete valid 0–100% daylight samples. Missing or invalid
cloud is never clear sky. Missing rain or one layer cannot erase the other
layers. Coverage is recorded independently in `cloud_coverage`. Cloud-only
forecasts are retained separately in `model.cloud_daily`, so a short sunshine
feed need not conceal a longer cloud forecast. Availability follows real data,
not the advertised maximum model horizon.

**Advisory** `review_flags` identify estimated sunshine of at least 80% of daylight
alongside total cloud of at least 90%, or low/medium cloud of at least 80%.
All available layer amounts accompany the message; high-cloud dominance is
identified only where all relevant layers are complete, with unknown optical
thickness explicitly noted. These are uncalibrated review thresholds, not
probabilities, rejection criteria or numerical sunshine corrections. Daily
means do not establish that clouds and sunshine occurred simultaneously.

See [cloud calculation and limitations](docs/cloud-method.md). Quality version:
`2026-10-10.2`. Sunshine still requires independent observational validation.

## Forecaster cross-check with EPD (10–14 October 2026)

`data/epd_reference.json` contains a limited, manually transcribed comparison
from five user-supplied EPD probabilistic sunshine charts: the central value,
10th and 90th percentiles at three geographically matched Scottish stations.
It is not the full EPD inventory, an observation archive or a calibration dataset.
Source run, exact station identity and accumulation window are not independently
confirmed. Missing station/date references are unknown, not zero.

The dashboard highlights deterministic estimates outside the displayed EPD
percentile interval with a 0.5-hour allowance for whole-hour rounding, but does
not reweight, suppress or alter them. Forecast disagreement alone does not
establish which system is more accurate.

## Data

ECMWF IFS, GFS, UKMO Global and UKV are requested separately from Open-Meteo's Single Runs API.
The latest common **00 UTC** cycle is used; if unavailable, the previous day's 00 UTC cycle is tried.
Hourly sunshine accumulations are summed at endpoints 01 UTC through the following 00 UTC.
All 24 sunshine intervals at all 20 stations must exist before a model/day has sunshine output.
Supporting radiation must pass physical checks at each station before its amount is displayed.
Physical failures are `null` in `daily` and shown as a gap (—); unavailable sunshine days remain absent.
Cloud and rain are independent context, never a reason to alter or suppress a sunshine amount.
Cloud-only dates do not manufacture missing sunshine totals.

Rounding on maps is to the nearest whole hour, with halves rounded up, after summation.
Provider-reported totals remain in each day's `quality` entries, separate from screened values.
Maximum query windows are 15 days for IFS, 16 for GFS, 7 for UKMO Global, and 3 for UKV;
actual sunshine and cloud coverage are detected separately from returned data.

These are station/grid-cell estimates, not regional averages or native sunshine products.
They do not include ensemble percentiles and have not been calibrated to ePD or observations.
Open-Meteo's sunshine algorithm uses a linear 60–180 W/m² DNI ramp around the 120 W/m² threshold.
Hourly mean irradiance cannot determine how many minutes the sun was visible within an hour;
interpolation from longer model steps further limits precision. This is not native ECMWF `sund`.

## Physical quality screening and daylight

The updater validates model-specific requests, UTC timestamp continuity, station/grid distance,
units, all 24 sunshine intervals, physical ranges and supporting radiation completeness.
Direct horizontal radiation must not exceed total horizontal radiation; diffuse radiation must
not be materially negative. A 2 W/m² tolerance permits rounding noise. Sunshine must fit NOAA's
apparent daylight window, allowing 2 minutes of geometry/refraction tolerance.

Sunrise and sunset use the full Gregorian date and NOAA/Meeus Julian-century equations,
iterated at each event; leap years and changes of season are automatic. Station-table daylight
uses each named station's coordinates. Model QC and cloud means use corresponding grid-cell
coordinates. The horizon is flat at sea level with standard refraction (90.833° zenith),
excluding twilight, terrain shading and local obstructions. Calculations remain in UTC.
Daylight is shown in hours and minutes; sunshine is checked before rounding to whole hours.
An 11-hour display can be valid for an unrounded 10.6-hour forecast within a 10h 50m day.
Five independent US Naval Observatory reference cases cover north/south locations, summer,
winter, autumn and a leap day; sunrise and sunset agree within one minute in those cases.

No cloud/rain thresholds suppress or reduce sunshine amounts. The former unvalidated screens
were removed on 9 October 2026. Thin cloud and showers can coexist with sunshine.
Passing physical checks does not demonstrate forecast accuracy. Rain is not fractionally
split at sunrise/set. See the cloud-method document for the separate temporal cloud integration.

The [native-source assessment](docs/source-assessment.md) records access and definition limitations.
Real GFS SUNSD records and Met Office inventories are preserved in
`data/source-investigation-2026-10-09.json`; these diagnostics do not supply map values.
`data/hourly.json` retains source fields/timestamps and `data/audit-2026-10-09.json` preserves
original evidence independently of later refreshes. Regression fixtures include actual
Kinloss, Bishopton and Cork data from that audit.
See the [provider algorithm](https://github.com/open-meteo/open-meteo/blob/f625df2c2b2d29d7837b1c71660fb226b1864f9b/Sources/App/Helper/Solar/SunRiseSet.swift)
and [NOAA solar geometry](https://gml.noaa.gov/grad/solcalc/calcdetails.html).

The generic RoI row is excluded until a station or area-averaging definition is supplied.
Station-coordinate sources are recorded in `data/stations.json`; Natural Earth 1:10m map
geometry is simplified and projected with a Lambert conformal conic projection.

## Refresh and publish

GitHub Pages must use **GitHub Actions** as its source. `.github/workflows/pages.yml` checks updates
at 02:17, 08:17, 14:17 and 20:17 UTC and on pushes/manual runs. Schedules can be delayed.
Each successful refresh commits the snapshot before publishing. Python regression tests
and JavaScript syntax validation run before publication and on pull requests.
Failures stop deployment, preserving the last successful site. A stale-data notice appears
when retrieval is over 24 hours old or the model cycle is over 40 hours old.

No frontend credentials are required. Open-Meteo's hosted free service is for evaluation/non-commercial
use. For commercial operational use, configure an appropriate Open-Meteo subscription and add an
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
