# GloveIQ Flask API

The backend uses an application factory, SQLAlchemy models, Flask-Migrate, and
versioned blueprints. It is intentionally independent of upstream computer-vision and
sorting components. Records arrive through the documented JSON and CSV APIs.

Python 3.15 is supported. The analytics dependencies use compatible release ranges
because older pinned Pandas/NumPy/scikit-learn releases do not provide Python 3.15
wheels and would attempt a local C/C++ build on Windows.

## Local setup

```powershell
cd component4\backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Set `DATABASE_URL` to a MySQL URL in `.env` (for example
`mysql+pymysql://user:password@localhost:3306/gloveiq`). SQLite is used when it is
unset, which makes isolated tests and local prototyping possible.

## Migrations and demonstration data

```powershell
$env:FLASK_APP = "run.py"
python -m flask db upgrade
python -m scripts.seed
python -m flask --app run.py run --debug
```

After changing models, create and apply a migration with:

```powershell
python -m flask db migrate -m "describe the schema change"
python -m flask db upgrade
```

Demo rows are marked with `metadata_json.demonstration=true`; they are not live
factory measurements.

## API and schema

All new endpoints are under `/api/v1` and return `{ "data": ..., "meta": ... }` on
success or `{ "error": { "code": ..., "message": ... } }` on failure. Pagination
uses `page` and `per_page` (maximum 100). List endpoints accept `batch_id`,
`search`, `start_date`, and `end_date` where applicable. CSV imports use
`POST /api/v1/data-management/import` with multipart fields `file`, `record_type`,
and optional `preview=true`; imports are validated and committed transactionally.

The normalized schema is:

* `batches` stores batch identity and current status.
* `production_records`, `inspection_records`, `quality_records`, and
  `sorting_records` store source events linked to `batches`.
* `quality_alerts`, `prediction_records`, and `report_records` store derived
  operational artifacts.
* `audit_logs` records important changes and imports.

Source event quantities are not copied onto `batches`; dashboard totals are
calculated from event tables. Foreign keys, indexes, range checks, and quality-grade
checks are enforced by SQLAlchemy and the migration.

## Analytics contract

`GET /api/v1/analytics/descriptive` calculates all dashboard KPIs from the
production, inspection, quality, and sorting tables using Pandas and NumPy.
`GET /api/v1/analytics/trends` accepts `granularity=daily|weekly|monthly`,
`start_date`, `end_date`, and optional `compare=true`. A custom range is
represented by the date filters with daily buckets. `GET
/api/v1/analytics/decision-support` returns threshold warnings and does not
duplicate an alert whose metric and batch already has an Open or Acknowledged
alert.

KPI definitions and limitations:

* Production, inspected, accepted, and rejected quantities are sums of the
  corresponding `production_records` columns. Invalid or internally
  inconsistent rows are excluded and reported in `data_quality_warnings`.
* Inspection coverage is `inspected_quantity / production_quantity * 100`.
  Acceptance and rejection rates use inspected quantity as the denominator and
  are unavailable when that denominator is zero.
* Defect frequency counts `inspection_records` by `defect_category`. Defect
  rate is defect events / inspected quantity * 100; defect events are not
  assumed to be unique gloves or equal to rejected gloves.
* Grade distribution counts `quality_records.quality_grade` and includes
  explicit zero values for A, B, C, and Reject. Sorting success is successful
  `sorting_records` / all sorting records; it is unavailable for an empty set.
* Batch summaries aggregate production rows by `batch_id` and calculate each
  batch rejection rate with the same inspected-quantity denominator.
* Trend rows contain `period`, `date`, `value` (production quantity), the four
  quantity totals, and period rejection/acceptance rates. A comparison is
  returned as `unavailable` when the previous comparable period has no records.

Missing, invalid, duplicate, and inconsistent records are never silently
treated as valid analytics input. The service normalizes timestamps to UTC,
trims categorical values, coerces numeric values only for validation, and
returns warnings describing excluded or incomplete data.

## Predictive quality-risk model

The predictive module uses one row per batch and a
`RandomForestClassifier(class_weight="balanced_subsample")`. A batch is labelled
`high_risk` when its historical rejection rate is at least
`QUALITY_REJECTION_THRESHOLD` (default 5%) or its Reject-grade share is at
least `REJECT_GRADE_THRESHOLD` (default 5%). Rejected quantity and quality
grade are label sources only and are excluded from model features. Training
requires valid production timestamps, positive production and inspected
quantities, at least two target classes, and both classes in chronological
training and evaluation windows. The default minimum is eight eligible
batches.

Features include production quantity, inspection coverage, inspection event
volume and category diversity, quality-record count and size/colour diversity,
sorting workload/failure count, production line, and dominant size/colour.
Sorting status and quality grade are not used as features. Training uses a
chronological 75/25 batch split, not a shuffled split, to reduce temporal
leakage. Evaluation reports accuracy, precision, recall, F1, confusion matrix,
and ROC-AUC when both evaluation classes are present. It also reports a
documented rule baseline based on low inspection coverage or elevated
inspection-event rate.

The model is persisted as Joblib plus JSON metadata in `component4/models`
(configurable with `PREDICTIVE_MODEL_DIR`). Run:

```powershell
python -m flask --app run.py db upgrade
curl -X POST http://127.0.0.1:5000/api/v1/predictions/train
curl http://127.0.0.1:5000/api/v1/predictions/status
curl -X POST http://127.0.0.1:5000/api/v1/predictions/predict `
  -H "Content-Type: application/json" -d '{"batch_id":"B-2026-001"}'
```

Risk categories use configurable model probability thresholds:
Low `< 0.33`, Medium `0.33–0.65`, and High `>= 0.66`. A prediction is an
estimate, not a guarantee of future defects. The API explicitly returns
`untrained`, `insufficient_data`, `unavailable`, or `failed` states instead of
inventing probabilities or evaluation results.

## Alerts and reports

`POST /api/v1/alerts/generate` evaluates current analytics and completed model
predictions. Rule conditions and ML conditions are labelled separately in the
`source` field. An active condition is deduplicated by triggering metric and
batch until the existing alert is resolved. `GET /api/v1/alerts` supports
`search`, `severity`, `batch_id`, `start_date`, `end_date`, and `status`;
`GET /api/v1/alerts/summary` provides active severity counts. Alert status can
be changed with `PATCH /api/v1/alerts/<id>` using `Open`, `Acknowledged`, or
`Resolved`.

Reports support `daily-production`, `batch-quality`, `defect-analysis`,
`rejection-acceptance`, `historical-trend`, and `predictive-risk`. Use
`POST /api/v1/reports/preview` with `report_type`, optional `start_date`,
`end_date`, and `batch_id` before exporting. `POST /api/v1/reports/export`
accepts the same fields plus `format=csv|pdf`, streams the generated file, and
retains generation metadata in `report_records`. Exports contain measured
database values, selected period, generation time, metrics, findings, and
available rows; unavailable values remain explicitly empty.

## Test

```powershell
python -m pytest tests -q
```
