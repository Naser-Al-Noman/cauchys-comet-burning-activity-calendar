# Planned method

This document describes the analysis and product logic we plan to implement. Nothing below has been run or validated in this repository yet.

## 1. Clean detections and harmonize confidence

We will download MODIS and VIIRS active-fire detections from NASA FIRMS and apply consistent quality filters (for example, dropping clear duplicates and applying agreed confidence thresholds once we finalize them against the challenge requirements).

MODIS reports confidence on a 0–100 scale; VIIRS uses categorical levels (low, nominal, high). We will map both to a common ordinal or numeric confidence scale so that downstream aggregation treats the sensors consistently. The exact mapping will be documented in code when we implement it.

## 2. Aggregate to a common grid

We will aggregate detections to a shared spatial grid with cells of about 5.5 km and a weekly time step. Each cell-day will count at most once toward activity metrics (one detection flag per cell per day, regardless of how many raw points fall in that cell on that day). This grid will be the basis for calibration, baselines, and the calendar views.

## 3. Calibrate MODIS against VIIRS

For years when both MODIS and VIIRS collected data over the same region, we will calibrate MODIS-derived grid counts to match the distribution of VIIRS-derived counts. We plan to use quantile mapping applied separately by geographic region and season (for example, monsoon vs dry season), so that harmonized MODIS years are comparable to VIIRS years before we merge long-term records.

## 4. Week-of-year baseline and anomaly score

On the harmonized weekly grid we will build a baseline for each cell (or for regional aggregates) by week of year, using historical years that pass our quality checks. The baseline will include percentile bands (for example, median and upper/lower tails). For a given week we will compute an anomaly score that compares observed activity to that baseline, so users can see whether a week is typical or unusual.

## 5. Critical periods and shifting peaks

We will rank weeks or short windows that historically show the highest burning activity and label them as critical periods for planning and awareness. We will also track whether the timing of peak activity shifts over the record—for example, earlier or later peaks in recent decades—using the harmonized timeline only, with clear notes where record length differs pre- and post-VIIRS.

## 6. Validation and limitations

We plan to validate the harmonized product in several ways:

- **Sensor transition years:** Compare behavior in years when both MODIS and VIIRS were active, before and after applying calibration.
- **Held-out years:** Reserve some years from calibration and test whether baselines and anomalies behave plausibly on those years.
- **Burned area:** Compare detection-based metrics to MODIS MCD64A1 burned-area products where spatial and temporal overlap is meaningful.

We will state limitations explicitly in the product and documentation:

- Cloud cover and smoke can hide or confuse active-fire detections.
- Small fires may be missed, especially at coarser effective resolution after aggregation.
- Hot-spot detections indicate thermal anomalies at detection time; they are **not** the same as mapped burned area or fire intensity on the ground.

No validation results or accuracy numbers will be claimed until we have implemented the pipeline and completed those checks.
