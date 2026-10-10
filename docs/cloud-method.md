# All-model cloud use — 10 October 2026

Quality version: `2026-10-10.2`. This supersedes the former total/low-only
cloud summaries described in the original README. There is no calibrated
cloud-to-sunshine correction in this release.

## Inputs and model identity

Every explicit Single Runs request for IFS, GFS, UKMO Global and UKV includes
`cloud_cover`, `cloud_cover_low`, `cloud_cover_mid` and `cloud_cover_high`.
They remain associated with the same requested model, run, hourly timestamps
and returned grid point as its radiation. No cloud field is borrowed from
another model; none is inferred from an EPD forecast or another station.

Provider total cloud is retained rather than obtained by adding the layers.
Cloud layers overlap and their definitions/derivations can differ by model.
No claim is made that all four providers use identical vertical boundaries.

## Temporal aggregation and missing data

Cloud percentages are instantaneous hourly samples in the API. Between each
pair, assume linear evolution and integrate only the portion falling between
model-grid sunrise and sunset, using the existing NOAA/Meeus solar geometry.
The daily mean is the sum of these integrals divided by daylight duration.
This corrects the former full-hour endpoint averaging of partial sunrise/set
intervals. It is an interpolation assumption, not measured sub-hourly cloud.
Night-time cloud does not dilute the sunshine-relevant daylight mean.

Each field independently needs valid numeric 0–100% samples at every endpoint
bracketing daylight. Boolean, null, non-finite, out-of-range and absent values
are not clear sky. An incomplete field has no published daily mean, and its
coverage is recorded in `cloud_coverage`. Other valid layers are retained.
Missing rain does not remove cloud data. Whole precipitation intervals that
touch daylight are retained separately, never fractionally apportioned.

`model.cloud_daily` stores cloud contexts separately from sunshine totals, so
complete clouds remain accessible after the shorter radiation/sunshine horizon
and on days where sunshine fails physical QC. Coverage is computed from actual
returned data; a model's advertised maximum range is not assumed available.
The date selector admits cloud-only days with an explicit label when no
selected model has a complete sunshine day.

## How clouds affect the output

All four fields are displayed in the station-selectable cloud comparison and
all-station quality table, and in sunshine map/table tooltips. The sunshine
figures themselves remain the original, physically screened radiation estimate.

High estimated sunshine (at least 80% of daylight) with total cloud at least
90%, or either low or medium cloud at least 80%, prompts advisory review. All
available layer amounts accompany the message. High-cloud dominance (high at
least 80%, low and medium at most 20%, all three complete) is identified as
context with explicitly unknown optical thickness. These numerical thresholds
are uncalibrated review heuristics, not probabilities or physical rejection
criteria. They never multiply, cap, replace or suppress sunshine.

Daylight-average cloud and accumulated sunshine do not prove temporal
coincidence. Thin high cloud may transmit bright sunshine. Even low/mid cloud
area fractions are not direct measurements of beam attenuation. Independently
observed sunshine with matching periods is still required for calibration.

## Verification

Regression tests cover all four explicit model requests, separate model values,
all layers, sunrise/set partial intervals, night exclusion, independent missing
rain/layers, absent arrays, invalid percentages, cloud-only dates, and unchanged
sunshine totals/physical status. Existing solar and source-physics tests remain.

Primary API definitions:
- https://open-meteo.com/en/docs
- https://open-meteo.com/en/docs/ecmwf-api
- https://open-meteo.com/en/docs/gfs-api
- https://open-meteo.com/en/docs/ukmo-api
- https://open-meteo.com/en/docs/single-runs-api
