# Sunshine comparison — retired

**Retired on 12 October 2026. Automated sunshine forecast production has stopped. No restart is scheduled.**

The forecaster requested a review of meaningful improvements and retirement if none could be justified. The current radiation-derived four-model sunshine-hours comparison did not establish sufficient reliability for its intended forecasting use. Rather than apply further unvalidated cloud/radiation adjustments, its operational-looking maps have been replaced with a retirement notice.

This is not a claim that every forecast was wrong, that EPD is observational truth, or that sunshine prediction is impossible. It is a decision to stop this implementation until there is evidence for a materially better input or independently validated method.

## Decision and evidence

Read the [12 October retirement assessment](docs/retirement-assessment-2026-10-12.md) for the source review, reproducible snapshot identity, 700 checked station-day totals, current model availability and the limitations of comparison with the saved EPD forecasts.

The last reviewed snapshot used **12 October 2026, 00 UTC** runs and was retrieved at **09:14:53 UTC**. Saved forecast dates after retirement are historical model predictions, not maintained current guidance. Passing internal arithmetic or physical checks does not demonstrate forecast skill.

## Preserved research

- [Original source investigation](docs/source-assessment.md) and [cloud-method documentation](docs/cloud-method.md).
- [Forecast snapshot](data/forecast.json), [raw hourly fields](data/hourly.json), [station definitions](data/stations.json) and [limited EPD screenshot reference](data/epd_reference.json).
- [9 October radiation audit](data/audit-2026-10-09.json) and [native-source investigation](data/source-investigation-2026-10-09.json).
- Calculation scripts, browser code, map assets and regression tests remain in the repository. The previous dashboard and guide are retained in [the pre-retirement version](https://github.com/matthewhugo81-arch/sunshine-comparison/tree/527ec1bc6fde0290d2f463a6f279b2b6228010b5).

The mapping and cloud diagnostics may be reused in a separately justified project. They are not a basis for inventing replacement sunshine totals or making unverified claims of improvement.

## Publication and maintenance

`.github/workflows/pages.yml` has **no schedule, provider requests, forecast refresh step or snapshot commit step**. It runs local regression checks and publishes static retirement/archive material only on a push to `main` or an explicit manual dispatch. Its repository-contents permission is read-only. No private API key is required for this workflow.

The landing page does not load `app.js` or request forecast data. Preserved JSON and scripts are research material, not active forecasts. No other weather repository or site was changed as part of retirement.

Local checks for preserved code (Python 3.12+ and Node):

```sh
python -m unittest discover -s tests
node --check app.js
```

Reconsider production only with documented, accessible sunshine-duration products for the named models, or a derived estimator with useful held-out observational verification at matched stations, accumulation windows, seasons and forecast lead times. Native output would still require verification. There is no automatic restart mechanism.

## Attribution and access

Original forecast data: ECMWF / NOAA / UK Met Office via Open-Meteo. Map boundaries: Natural Earth (public domain). Retained derived forecast datasets, maps and project material are offered under [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/).

The original provider's access and licensing terms still apply to any future reuse or retrieval. Do not put private API keys into frontend code or public data. See [Open-Meteo terms](https://open-meteo.com/en/terms) and [UKMO API attribution](https://open-meteo.com/en/docs/ukmo-api).
