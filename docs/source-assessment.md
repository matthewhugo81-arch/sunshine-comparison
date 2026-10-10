# Sunshine source assessment — 9 October 2026

**A reliable four-model bright-sunshine comparison is not yet established.** The
page still presents provisional Open-Meteo radiation estimates. Removing the
unvalidated cloud/rain screens corrects a screening mistake, not the underlying
sunshine method. Physical source failures remain null and are never filled with
zero, the old invalid estimate, daylight, or an invented lower number.

## EPD independent probabilistic comparison — 10 October 2026

Five EPD sunshine maps supplied by the forecaster (valid 10–14 October 2026)
show a notably less sunny scenario than the provider-derived GFS in several
cases. For example, EPD Kinloss on 12 October is central 0 h (10th 0 h,
90th 4 h), whereas the current GFS-derived estimate is around 9 h in
100% mean total cloud. The 14 October GFS-derived sunshine estimates are
also notably larger than EPD central estimates at many stations.

The published machine-readable reference contains only 15 manually transcribed
station/date samples across Kinloss, Glasgow (Bishopton) and Edinburgh Gogarbank.
We have not inferred missing stations or given the screenshot-based values a
verified source cycle. This evidence justifies quality investigation but cannot
justify overwriting any deterministic forecast with EPD estimates.

Next step: obtain EPD's original timestamped station quantiles and accumulation
definitions, then align valid dates, issue times and geographical sampling.
Separately score all providers against **observed** sunshine duration by
station, lead time and season, with missing-data and rounded-zero handling.

## What was checked

| Model/source | Finding | Decision |
| --- | --- | --- |
| Open-Meteo, all four requested models | Sunshine is derived from mean direct radiation using a 60–180 W/m² DNI ramp. The mean does not identify the duration above 120 W/m² within an interval. | Retain only as an explicitly provisional estimate. No accuracy claim from passing physical checks. |
| IFS HRES 9 km through Open-Meteo | The `ecmwf_ifs` mapping uses `EcmwfEcpdsReader`. It reads native `fdir` and `ssrd` radiation, interpolates them, and derives sunshine. It does **not** read native `sund`. | Do not confuse this with the 0.25-degree IFS reader's empirical direct/diffuse separation. The stage causing the inconsistent radiation has not been isolated. |
| ECMWF public IFS subset | The current published parameter list includes `ssrd`, but not `sund` (189). ECMWF's wider catalogue is available through service agreements. | No accessible native sunshine feed has been established for this project. Open Charts are not a documented station-data API. |
| NOAA GFS native `SUNSD` | Real 00 UTC GRIB records for the challenged date were downloaded and decoded at all 20 stations. Units are seconds; GRIB labels the field instantaneous. Sample record maxima were 21,600 seconds. | Do not treat it as an hourly sum or cumulative run total. Records are preserved for investigation, without substituting them into the maps. |
| GFS physics diagnostic | The inspected CCPP implementation accumulates model timesteps when `adjsfcdsw / xcosz >= 120`; metadata identifies `adjsfcdsw` as total surface downwelling shortwave flux, not the direct component. | Native naming alone does not establish comparability with WMO direct-beam sunshine. Operational version/definition and output reset periods must be established before adoption. |
| Met Office deterministic open data | Complete listings of 4,527 Global objects (70 parameters) and 3,788 UKV objects (52 parameters) were inspected. No sunshine-duration parameter name was found. Direct/total radiation exists through +168 h for Global and +54 h for UKV. | Global radiation extends beyond the current API sunshine feed's two complete days, but it still needs a defensible duration calculation. Changing endpoint alone does not supply native sunshine. |
| Met Office blended probabilistic sunshine | The provider describes it as a technical-prototyping diagnostic. It is also a blended product, not separate UKMO Global and UKV deterministic output. | Not a drop-in replacement for these two columns. |

The cloud/rain screens removed on this date had no observational calibration.
Cloud cover is an area fraction, and rain can occur in showers or alongside sun;
neither is sufficient evidence to override a numerical sunshine estimate. Their
removal does not validate a restored provider estimate. Cloud and rain remain
available as context, and missing optional context no longer suppresses an
otherwise complete radiation estimate.

## Preserved evidence

- [Original IFS/GFS radiation audit](../data/audit-2026-10-09.json).
- [Native-source investigation](../data/source-investigation-2026-10-09.json):
  exact GFS object URLs, byte ranges, SHA-256 hashes, GRIB metadata and sampled
  station values; full Met Office parameter inventories and lead times.
- The regression fixture still rejects Kinloss's 13 October IFS values: at
  08 UTC total/direct/diffuse were 5.1/35.6/−30.5 W/m²; at 09 UTC they were
  27.9/118.1/−90.2 W/m². Replacing those values with clipped direct radiation
  would not recover the missing sunshine duration.

To reproduce the native investigation, install the optional `eccodes` Python
package in an isolated environment and run:

```sh
python scripts/audit_native_sources.py --run 2026-10-09T00:00 --date 2026-10-13 --output work/source-investigation.json
```

The audit is separate from the forecast updater and never supplies map values.
Use a current run when a source's rolling archive no longer retains this run.

## Primary sources

- [Open-Meteo IFS HRES reader](https://github.com/open-meteo/open-meteo/blob/f625df2c2b2d29d7837b1c71660fb226b1864f9b/Sources/App/EcmwfEcpds/EcmwfEcpdsReader.swift)
  and [sunshine calculation](https://github.com/open-meteo/open-meteo/blob/f625df2c2b2d29d7837b1c71660fb226b1864f9b/Sources/App/Helper/Solar/SunRiseSet.swift).
- [ECMWF open-data parameters](https://www.ecmwf.int/en/forecasts/datasets/open-data)
  and [service agreements](https://www.ecmwf.int/en/forecasts/accessing-forecasts/service-agreements).
- [CCPP GFS diagnostic implementation](https://github.com/NCAR/ccpp-physics/blob/f601ce98397d497055b0b46fc680ef86232298ff/physics/Interstitials/UFS_SCM_NEPTUNE/GFS_suite_interstitial_2.F90)
  and [variable metadata](https://github.com/NCAR/ccpp-physics/blob/f601ce98397d497055b0b46fc680ef86232298ff/physics/Interstitials/UFS_SCM_NEPTUNE/GFS_suite_interstitial_2.meta).
- [NOAA postprocessor reading `sunsd_acc`](https://github.com/NOAA-EMC/UPP/blob/cd68e265ff4431d21efcaa5ce3c7c5a91244c0ad/sorc/ncep_post.fd/INITPOST_NETCDF.f)
  and [NOAA's notice of the instantaneous time label](https://www.emc.ncep.noaa.gov/emc/pages/numerical_forecast_systems/gfs/implementations.php).
- [Met Office open-data registry](https://registry.opendata.aws/met-office-global-deterministic/)
  and [blended sunshine product status](https://datahub.metoffice.gov.uk/support/changes-and-updates).

## What is still needed

For a genuine native comparison: documented sunshine-duration products for each
named model, including run identity, accumulation period, units, model grid and
redistribution access. For a derived comparison: an independently tested method
using sufficient radiation/cloud inputs, with held-out sunshine observations
across UK/Irish seasons and forecast lead times. A daylight bound is necessary
but does not demonstrate that a sunshine estimate is correct.

No service was purchased and no data provider was contacted.
