# Cauchy's Comet: The Burning Activity Calendar

## Problem

MODIS active-fire detections at about 1 km resolution have been available since 2000, while VIIRS detections at about 375 m resolution have been available since 2012. These two records are not directly comparable: differences in spatial resolution, overpass timing, and confidence reporting can make a year look like a “record high” for fire activity when part of the signal is a sensor or processing artifact rather than a true change on the ground. We plan to build a calendar-oriented view that harmonizes the two sensors before comparing weeks or seasons across years.

## Questions the app will answer

1. **When does this area normally burn?** We will summarize typical burning activity by week of year for a chosen region.
2. **Is this week unusual compared with past years?** We will compare the current week to a harmonized historical baseline and flag anomalies.
3. **Which periods are critical, and are they shifting?** We will rank high-activity periods and track whether peak timing moves over time.

## Planned approach

We will ingest NASA FIRMS hot-spot archives for MODIS and VIIRS, clean and filter detections, put confidence on a common scale, and aggregate both sensors to a shared spatial and temporal grid. During years when both sensors operated, we will calibrate MODIS to VIIRS using quantile mapping by region and season. On that harmonized record we will build week-of-year baselines, anomaly scores, and summaries of critical burning periods. Details are in [docs/method.md](docs/method.md).

## Planned data sources

We plan to use NASA FIRMS (MODIS and VIIRS), MODIS MCD64A1 burned area for validation, NASA POWER, and NASA GIBS for context layers. Geographic focus is South Asia, with Bangladesh as the demonstration area. See [docs/data_sources.md](docs/data_sources.md).

## Project status

This repository is a **concept-stage proposal** for Team Cauchy's Comet in the [NASA International Space Apps Challenge 2026](https://www.spaceappschallenge.org/) (Bangladesh), challenge **“Harmonization of MODIS and VIIRS Hot Spots.”** Nothing here is a working product yet: there is no deployed app, no finished pipeline, and no reported results. Descriptions of method, data, and software layout are plans for work we intend to do during the challenge.

## Team

All team members are from Bangladesh:

- Naser-Al-Noman
- Zaid Rehman
- Sadman Zaman Khan
- Muhammad Junayed
- Md. Meheraj Hossain
- Israt Jahan Lamia

## Data credit

Data: NASA FIRMS (MODIS, VIIRS)

## License

This project is licensed under the Apache License 2.0. See [LICENSE](LICENSE).
