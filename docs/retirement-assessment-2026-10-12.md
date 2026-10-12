# Sunshine comparison: retirement assessment

**Decision date: 12 October 2026. Status: retired; no restart scheduled.**

The forecaster requested a further assessment of meaningful improvements, with retirement if none could be justified. The current four-model sunshine-hours product is retired. This is a decision about the fitness of this implementation for its intended forecasting use, not a claim that sunshine prediction is impossible or that every published amount is wrong.

Scheduled forecast retrieval and snapshot commits have been removed from the Pages workflow. The landing page is now a retirement notice and does not load the forecast application. Code, tests, raw snapshots and prior versions remain in the repository. The workflow only publishes static material on a push or explicit manual dispatch. No other repository or website is changed.

## Evidence inspected

- The latest successful pre-retirement Pages publication: [run 38228613945](https://github.com/matthewhugo81-arch/sunshine-comparison/actions/runs/38228613945), artifact 11737251956.
- Its actual packaged `data/forecast.json`, `data/hourly.json`, station list, EPD reference and browser files, rather than assuming the README described the deployed data.
- Snapshot retrieval: **12 October 2026, 09:14:53.905676 UTC**. All four requested model cycles: **12 October 2026, 00 UTC**.
- Forecast JSON SHA-256: `6ec180cd568157f9939d96111907d6c1f93e7d98560d25d9110f7a31123b5a4c`.
- Production aggregation and screening code, the previous native-source investigation, current Open-Meteo sunshine implementation, ECMWF's public parameter list and the Met Office product-status documentation.

Direct rendering of the public Pages URL was unavailable to the review browser. The deployed artifact and successful deployment record were therefore used to inspect the exact published contents; no claim is made that an interactive browser test was performed during this review.

## Arithmetic and timing checks

Independent recalculation summed the 24 preceding-hour sunshine intervals ending at 01 UTC through the next day's 00 UTC, divided by 3,600, and compared the result with each stored unrounded provider total. Displayed non-null totals were also checked. Tolerance was 0.00000501 hours for the stored five-decimal rounding.

| Model | Station-days checked | Sum mismatches | Timestamp continuity failures | Withheld station-days |
|---|---:|---:|---:|---:|
| ECMWF IFS | 300 | 0 | 0 | 4 |
| GFS | 320 | 0 | 0 | 0 |
| UKMO Global | 40 | 0 | 0 | 0 |
| UKV | 40 | 0 | 0 | 0 |
| Total | 700 | 0 | 0 | 4 |

These checks establish internal aggregation consistency, not forecast skill. All four withheld IFS station-days are across the full saved horizon; none is for 14 October. Older radiation failures documented in the 9 October audit must not be presented as new failures of the 14 October snapshot.

## The requested valid date: 14 October 2026

| Station | IFS hours, 12 Oct 00 UTC | GFS hours, 12 Oct 00 UTC | EPD central (P10–P90), screenshots supplied 10 Oct |
|---|---:|---:|---:|
| Kinloss | 0.28699 | 6.23371 | 2 (0–8) |
| Glasgow (Bishopton) | 3.20323 | 7.35038 | 0 (0–6) |
| Edinburgh Gogarbank | 6.30960 | 9.75739 | 1 (0–7) |

**This is not matched-cycle verification.** The EPD source cycle, exact station identity and accumulation definition were not independently established. EPD is another forecast, not an observation. Its central value must not be assumed to be a verified mean or median. Some deterministic amounts remain inside the broad EPD interval. Agreement with EPD cannot serve as the calibration target or proof of skill.

Across the 20 stations, the IFS arithmetic mean was 6.3907555 hours and the GFS mean 9.355989 hours. These are means of the sampled stations, not UK/Irish area averages.

GFS Cork Airport gave 9.68806 sunshine hours with daylight-mean total cloud 99.7%, low cloud 40.7%, medium cloud 87.9% and high cloud 90.9%. Edinburgh Gogarbank gave 9.75739 hours with 100% total and high cloud. These warrant meteorological scrutiny but are not physical proof of error: cloud fraction is not cloud optical depth, and daily means do not resolve simultaneous cloud/sunshine behaviour. In particular, high cloud can transmit sufficient direct sunlight.

Neither UKMO Global nor UKV had a complete sunshine total for 14 October in this snapshot. Both sunshine series ended on 13 October. Global cloud continued through 18 October; UKV cloud ended on 13 October. A longer cloud horizon is not a sunshine-duration forecast and was not substituted for one.

## Why another numerical adjustment is not justified

The current Open-Meteo implementation derives sunshine from backwards-averaged direct horizontal radiation and solar geometry. In a fully sunlit interval, its DNI-to-duration conversion is a linear ramp from zero at 60 W/m² to the full interval at 180 W/m², centred on 120 W/m². Sunrise and sunset limit the interval.

Primary implementation inspected: [SunRiseSet.swift](https://github.com/open-meteo/open-meteo/blob/main/Sources/App/Helper/Solar/SunRiseSet.swift), blob SHA `81076e4246839244d6916f5b75efcd72706ffdee`, function `calculateBackwardsSunshineDuration`. The [general API documentation](https://open-meteo.com/en/docs) describes the sunshine threshold and preceding-hour interval convention.

An illustrative calculation, not an observed case: 600 W/m² DNI for 20 minutes and zero for 40 minutes has an hourly mean of 200 W/m². Persistent DNI of 200 W/m² for all 60 minutes has the same mean. The former has 20 minutes above 120 W/m²; the latter has 60. A duration estimate based only on that mean cannot distinguish them, and the current ramp assigns a full hour to either mean in full daylight.

This demonstrates the missing information; it does not prove that this particular intermittency pattern explains each disputed forecast. Spatial averaging, radiation processing and genuine cloud-forecast differences can also matter.

Total, low, medium and high cloud were already incorporated into daylight diagnostics. Adding those same fields again cannot recover cloud optical depth, overlap and sub-hourly passage over a station. Multiplying sunshine by clear-sky fraction, raising the radiation threshold or forcing values towards EPD could lower the numbers, but no independent verification establishes that these changes improve accuracy. Artificially interpolating hourly fields to finer timestamps adds no independent weather information.

## Alternative-source assessment

| Candidate | Finding | Decision |
|---|---|---|
| ECMWF native sunshine duration (`sund`) | Not listed in the current public IFS subset checked. The existing IFS API path derives sunshine from radiation rather than ingesting `sund`. | Potential reconsideration only with confirmed access to an appropriate documented product; no accessible replacement was established here. |
| NOAA native GFS `SUNSD` | The preserved source investigation found unresolved operational-definition/reset-period questions, including a diagnostic implementation using total rather than direct shortwave radiation. | A variable name alone does not establish a WMO-comparable replacement. The operational definition was not newly resolved in this review. |
| Direct Met Office deterministic radiation | The earlier inventory audit found longer radiation coverage than the API sunshine feed, but not a native sunshine-duration parameter. | May improve availability, not demonstrate duration accuracy. Not a rescue of the current four-model comparison by itself. |
| Met Office blended probabilistic sunshine | The currently retrieved provider status page describes the diagnostic as for technical prototyping. A blended product is not separate Global and UKV deterministic output. | Not a demonstrated drop-in replacement. |
| Observation-calibrated derived estimate | A feasible separate development path, but no matched independent verification sample or held-out skill result exists in this project. | Do not launch a new calibration project or claim improvement merely to keep this site alive. |

Sources checked on 12 October 2026: [ECMWF open data](https://www.ecmwf.int/en/forecasts/datasets/open-data); [Met Office product changes/status](https://datahub.metoffice.gov.uk/support/changes-and-updates); [Open-Meteo UKMO documentation](https://open-meteo.com/en/docs/ukmo-api); [Single Runs API](https://open-meteo.com/en/docs/single-runs-api). The detailed previously preserved native-source evidence is in [source-assessment.md](source-assessment.md) and [source-investigation-2026-10-09.json](../data/source-investigation-2026-10-09.json). No provider was contacted and no subscription or data service was purchased.

## Reconsideration threshold

Restart only if there is a materially better, documented and accessible sunshine-duration input for the named models, or an observationally tested estimator that demonstrates useful held-out performance at matched stations, accumulation windows, seasons and forecast lead times. Native model output would still need verification; native does not automatically mean accurate.

The conclusion is not that the experiment was worthless. The station mapping, cloud diagnostics, source audits and quality controls remain reusable. The specific operational-looking sunshine-hours comparison is not justified by the evidence presently available, so production has stopped rather than undergo another cosmetic or unvalidated numerical revision.
