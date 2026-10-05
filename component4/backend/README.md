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

## Test

```powershell
python -m pytest tests -q
```
