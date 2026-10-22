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

To populate the existing analytics pages with the real extracted COCO dataset,
run this idempotent import from `component4\backend`:

```powershell
python -m flask db upgrade
python -m scripts.import_coco_dataset --dataset ..\dataset
```

It creates three clearly marked audit batches (`DATASET-TRAIN`,
`DATASET-VALID`, and `DATASET-TEST`) using the actual image and annotation
counts. It also calculates a clearly labeled quality proxy from the annotations:
images with no annotated defect are `A`, one or two annotations are `B`, and
three or more are `Reject`; rejected quantity means images containing at least
one COCO annotation. These are dataset-analysis rules, not factory release
decisions or model predictions. Re-running the command refreshes these
dataset-audit records without touching unrelated production data.

Seeding is optional and inserts only clearly marked local demonstration records.
Remove those records without touching other data with:

```powershell
python -m scripts.reset_demo
```

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

## Batch quality-risk model

`dataset\glove_batch_quality_synthetic_dataset.csv` is the initial **synthetic
demonstration dataset**, not historical factory data. It contains 1,200 rows
with the labels Low, Medium, and High (1,108 High, 87 Medium, 5 Low at the
time of writing). Training reads this CSV and does not require copying it into
the operational tables.

The leakage-safe `RandomForestClassifier` uses only information available
before inspection: `production_line`, `shift`, `operator_experience_years`,
`machine_age_months`, `temperature_c`, `humidity_pct`, and production
quantity. Rejection counts/rates, acceptance, quality score, defect counts,
and the target label are never model features. Numeric imputation and
categorical one-hot encoding are persisted inside the Joblib pipeline.
`class_weight="balanced_subsample"` handles the severe class imbalance.
Training uses a stratified 75/25 split when class counts permit it and reports
the actual holdout accuracy, weighted precision, weighted recall, weighted F1,
and Low/Medium/High confusion matrix. Metrics from synthetic data are
demonstration results and do not establish real-world accuracy.

The model and JSON evaluation metadata are persisted in `component4\models`
(configurable with `PREDICTIVE_MODEL_DIR`). Configure the input file with
`PREDICTIVE_DATASET_PATH` when importing a replacement dataset with the same
schema. Run:

```powershell
python -m flask --app run.py db upgrade
curl -X POST http://127.0.0.1:5000/api/v1/predictions/train
curl http://127.0.0.1:5000/api/v1/predictions/status
curl -X POST http://127.0.0.1:5000/api/v1/predictions/predict `
  -H "Content-Type: application/json" `
  -d '{"batch_id":"B-2026-001","production_line":"Line-A","shift":"Morning","operator_experience_years":5,"machine_age_months":20,"temperature_c":25.0,"humidity_pct":65.0,"production_quantity":2000}'
```

`GET /api/v1/predictions/status` returns model readiness and measured
evaluation results. `POST /api/v1/predictions/predict` validates all
production-time fields and returns `risk_category`, `risk_probability`, and
`probability_scores` for all classes. For an existing database batch, the API
can derive production-time values from its records and metadata; a new batch
may submit the fields in the example and is stored with a pre-inspection
marker. Missing, non-numeric, negative, and non-finite values return clear
validation errors. Every stored result includes batch ID, timestamp, model
version, predicted risk, and probability scores.

## Hand-image dataset boundary

## Glove defect detection (Component 4)

The extracted dataset is at `component4\dataset\` and is not moved or modified.
The verified COCO splits are: train 62 images/79 boxes, valid 17/18, and test
9/9. Every referenced image exists, dimensions match the JSON, and all boxes
are positive and inside image bounds. Source category IDs 0 and 3 both carry
the generic name `defect-Detection`; the conversion preserves those IDs as
`Other defect`, while IDs 1 and 2 remain `Pinhole` and `Tear`.

Run these exact PowerShell commands from `component4\backend`:

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install -r ml\quality_detection\requirements.txt
python -m ml.quality_detection.validate_coco --dataset ..\dataset
python -m ml.quality_detection.train --dataset ..\dataset --epochs 30
```

Training copies images and generated YOLO labels into
`backend\ml\quality_detection\yolo_dataset`; original dataset files are never
overwritten. The script validates on the held-out `test` split and prints the
Ultralytics evaluation output. Copy the reported `best.pt` to
`backend\models\glove_defect_model.pt` (or set `DEFECT_MODEL_PATH`).

Detection endpoints are `/api/health`, `/api/predict`, `/api/batches`,
`/api/batches/<batch_id>/images`, `/api/batches/<batch_id>/summary`, and
`/api/analytics/overview`. Dataset and model readiness are available at
`/api/dataset` and `/api/training/status`. Batch analysis uses normalized image zones and
explicitly does not claim finger/palm/wrist localization because the COCO
annotations contain no anatomical region labels. For a presentation without
the optional YOLO runtime, use `GET /api/dataset/preview?split=test` through
the backend API. This is a clearly labeled COCO ground-truth audit of the
supplied images, not model inference, and therefore has no confidence score.
The supplied images consistently place the cuff on the left, palm in the
middle, and fingers on the right. The API therefore reports broad
`wrist/cuff`, `palm`, and `finger region` counts using an image-coordinate
heuristic. It cannot identify an individual finger or claim that the model
learned anatomical regions.

Start the API with `python -m flask --app run.py db upgrade` followed by
`python -m flask --app run.py run --debug`. If Ultralytics/model weights are
not installed, prediction returns HTTP 503 with the exact remediation rather
than fabricated results.

Check detector readiness with `GET /api/model/status` or `GET /api/health`.
`weights_available` only means the checkpoint file exists; `ready` means both
the checkpoint and the PyTorch/Ultralytics runtime are usable. The current
Python 3.15 environment cannot install the pinned PyTorch detector dependency,
so use Python 3.12-3.14 for real YOLO inference/training:

```powershell
py -3.13 -m venv .venv-yolo
.\.venv-yolo\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m pip install -r ml\quality_detection\requirements.txt
```

Batch quality is an image-based decision rule, separate from the detector:
`ACCEPT` means 0 observed detections, `REVIEW` means 1-2, and `REJECT` means
3 or more. Configure `DEFECT_REVIEW_COUNT` and `DEFECT_REJECT_COUNT` for a
demonstration-specific threshold. These are not industry-certified release
criteria, and no detection does not prove that a glove is defect-free.

The Google Drive hand-image dataset is not bundled with this repository. The
workspace audit found no project image files outside Python and frontend
dependencies, so no image count, class distribution, dimensions, corruption
check, duplicate check, or glove-versus-bare-hand determination can be made
yet. Do not train the quality-risk model from left/right image labels: those
labels represent an orientation-classification task, not a defective-versus-
acceptable production outcome.

If an image-classification supporting task is later approved, download the
dataset manually and place it under:

```text
component4\backend\data\raw\hand_images\
```

Use the class folders below for the current left/right organization:

```text
component4\backend\data\raw\hand_images\left\
component4\backend\data\raw\hand_images\right\
```

Then audit the files and labels before adding a separate image model. The
existing batch-level Random Forest remains the Component 4 quality-risk model
and requires labelled production history as described above.

The current dataset audit found 435 valid JPEG glove images at 2560x1440:
218 in `left` and 217 in `right`, with no corrupt files or exact duplicate
files. A separate grayscale pixel/gradient Logistic Regression classifier is
provided for this orientation-support task. It uses grouped capture-minute
splits and reports validation/test metrics; it does not predict defects,
acceptance, or batch quality risk.

Train it from `component4\backend`:

```powershell
python -m scripts.train_hand_orientation
```

Override paths when needed:

```powershell
$env:HAND_IMAGE_DATASET_DIR = "data\raw\hand_images"
$env:HAND_ORIENTATION_MODEL_DIR = "..\models\hand_orientation"
python -m scripts.train_hand_orientation
```

The saved Joblib model and JSON metadata are generated artifacts and should not
be treated as production validation without a representative independent test
set.

## Alerts and reports

`POST /api/v1/alerts/generate` evaluates current analytics and completed model
predictions. Rule conditions and ML conditions are labelled separately in the
`source` field. An active condition is deduplicated by title, triggering metric, and
batch until the existing alert is resolved. `GET /api/v1/alerts` supports
`search`, `severity`, `batch_id`, `start_date`, `end_date`, and `status`;
`GET /api/v1/alerts/summary` provides active severity counts. Alert status can
be changed with `PATCH /api/v1/alerts/<id>` using `Open`, `Acknowledged`,
`Under Review`, or `Resolved`.

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

## Component 3 live serial telemetry

The sorting dashboard reads live status from `GET /api/v1/sorting/live`. The
Flask process automatically starts `Drivers/interface.py` in a background
thread on its first request, so a separate driver terminal is not required.
Install the backend requirements and configure the serial port before starting
Flask:

```powershell
cd component4\backend
python -m pip install -r requirements.txt
$env:COMPONENT3_SERIAL_PORT = "COM7"
python -m flask --app run.py run --debug
```

Optional configuration:

```powershell
$env:COMPONENT3_BAUD_RATE = "115200"
$env:COMPONENT3_DRIVER_ENABLED = "true"
```

The firmware emits status every 100 ms. The backend writes it directly to the
in-process telemetry store and immediately pushes changes to the dashboard over
`GET /api/v1/sorting/stream` using Server-Sent Events. If no driver update
arrives within `SORTING_TELEMETRY_STALE_SECONDS`, the device is shown as offline. Set
`COMPONENT3_DRIVER_ENABLED=false` only when running the driver separately.

### Relay control mapping

The ESP32 firmware and backend use semantic commands instead of exposing raw
relay control through the dashboard:

* Relay 1: damaged-glove reject gate (`DEFECT_PULSE`)
* Relay 2: wrong-orientation reject gate (`ORIENTATION_PULSE`)
* Relay 3: dashboard-controlled camera LED
* Relay 4: latched consecutive-reject warning light

`SORT_RELAY_PULSE_MS` and `SORT_ACTUATION_DELAY_MS` in
`firmware/main_engine.ino` must be calibrated for the real pneumatic gate and
the distance from the camera to the actuator. The default pulse is 500 ms and
the default delay is zero. Disconnect actuator power while flashing or testing
new timing values.

The live orientation model automatically sends one decision per stable glove
observation. Configure the orientation allowed to remain on the main belt with
`SORTING_EXPECTED_ORIENTATION=LeftHand` or `RightHand`. Three consecutive reject
decisions latch the warning by default; change this with
`SORTING_WARNING_THRESHOLD`.

Component 1 can submit a final local damage/orientation decision from the same
computer. Defect takes priority over orientation for that decision:

```powershell
Invoke-RestMethod -Method Post `
  -Uri http://127.0.0.1:5000/api/v1/sorting/control/decision `
  -ContentType "application/json" `
  -Body '{"orientation":"RightHand","defective":true,"source":"component1"}'
```

Hardware-changing endpoints reject non-loopback clients. This keeps relay
actuation limited to the backend computer rather than the local network.

## Frontend checks

From `component4\frontend`:

```powershell
npm install
npm run build
```

The build performs the TypeScript check and creates the Vite production bundle.
No separate lint script is configured in the existing package.

## Live glove inspection

The Live Orientation dashboard starts the backend webcam only when the user
selects **Start model**. It loads the included MobileNet V2 TorchScript file for
`LeftHand`/`RightHand` classification and the Ultralytics YOLO checkpoint for
`defect-Detection`, `Pinhole`, and `Tear`. Both models share one webcam stream.
The browser receives smoothed orientation and defect results plus an annotated
MJPEG preview. A stable defect takes priority and sends `DEFECT_PULSE`; otherwise
the configured orientation rule determines whether `ORIENTATION_PULSE` is sent.

Only one vision model is loaded at a time. Starting the Live Orientation page
loads MobileNet only; starting the Live Defect Detection page stops the previous
mode and loads YOLO only. This avoids making every camera frame wait for both
CPU models.

Install the backend dependencies and start both applications:

```powershell
cd component4\backend
python -m pip install -r requirements.txt
python -m flask --app run.py run --debug

cd ..\frontend
npm install
npm run dev
```

Open `http://localhost:5173/live-orientation`. Optional settings in `.env` are
`ORIENTATION_CAMERA_INDEX`, `ORIENTATION_MIN_CONFIDENCE`,
`ORIENTATION_SMOOTHING_WINDOW`, `ORIENTATION_CLEAR_AFTER_FRAMES`, and
`ORIENTATION_MODEL_PATH`. Manual exposure is enabled by default with
`CAMERA_AUTO_EXPOSURE=false`, `CAMERA_EXPOSURE=-2`, and `CAMERA_GAIN=0` to avoid
washed-out inspection images. Set `CAMERA_AUTO_EXPOSURE=true` if automatic
exposure is preferred. The dashboard control changes the webcam's hardware
exposure directly within this camera's tested `-7` to
`-2` range; no software exposure filter is applied. Defect settings are `DEFECT_MODEL_PATH`,
`DEFECT_MIN_CONFIDENCE`, `DEFECT_IMAGE_SIZE`, and `DEFECT_INFERENCE_INTERVAL`.
Running YOLO every second frame by default reduces CPU latency. Low-confidence frames clear the previous stable result
and are displayed as `No glove / uncertain`. The default model
is `ml/quality_detection/weight/mobilenet_v2_classifier.torchscript.pt` and the
default defect model is `ml/defect_detection/weight/best.pt`. The default webcam
index is `0`.

On Windows, start the backend with the repository interpreter to avoid loading
a partially installed Microsoft Store copy of Torch:

```powershell
cd component4\backend
.\start_backend.ps1
```

If PowerShell script execution is disabled, use the interpreter directly:

```powershell
..\..\.venv\Scripts\python.exe -m flask --app run.py run --debug
```

## API endpoint groups

All responses use `{ "data": ..., "meta": ... }` on success and
`{ "error": { "code": ..., "message": ... } }` on failure.

* Dashboard: `/dashboard/summary`, `/dashboard/trends`
* Analytics: `/analytics/descriptive`, `/analytics/trends`,
  `/analytics/quality`, `/analytics/decision-support`
* Records: `/production`, `/batches`, `/batches/<batch_id>/quality`,
  `/history`, `/defects/summary`, `/defects/trends`, `/sorting/summary`
* Predictions: `/predictions`, `/predictions/status`,
  `/predictions/analytics`, `/predictions/train`, `/predictions/predict`
* Alerts: `/alerts`, `/alerts/summary`, `/alerts/generate`,
  `/alerts/<alert_id>`
* Reports: `/reports`, `/reports/preview`, `/reports/export`
* Data/configuration: `/data-management/summary`,
  `/data-management/import`, `/settings`

Genuine predictive evaluation requires at least the configured minimum number of
eligible historical batches, valid production quantities and timestamps, and both
target classes in chronological training and evaluation windows. With insufficient
history the API reports `insufficient_data` instead of fabricating accuracy or
risk probabilities.
