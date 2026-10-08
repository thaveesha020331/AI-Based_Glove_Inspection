# Component 4 — GloveIQ Quality Intelligence

Smart Quality Monitoring and Predictive Analytics Dashboard for the AI-based automated
quality inspection and sorting system for rubber gloves.

## Architecture

```
component4/
├── frontend/                 # Vite + React + TypeScript SPA
│   └── src/
│       ├── app/              # application shell and demo data
│       ├── components/       # reusable visual primitives
│       ├── features/         # domain pages
│       ├── layout/           # responsive sidebar and top navigation
│       ├── services/         # API boundary and typed client
│       ├── styles/            # design tokens and global styles
│       └── types/             # shared frontend contracts
├── backend/                  # Flask application
│   ├── app/                  # factory, config, blueprints, models
│   ├── analytics/            # Pandas/NumPy reporting services
│   ├── ml/                   # Random Forest training/inference
│   ├── repositories/         # SQLAlchemy persistence boundary
│   └── tests/
├── data/                     # local demo/import data
├── models/                   # generated joblib artifacts (ignored)
└── docs/
```

The application is a responsive Flask-backed dashboard. All normal screens read from
the versioned API through a configurable Axios client. Demo data is opt-in through the
backend seed script and can be removed with the reset script; the frontend never falls
back to fabricated values when the API is unavailable.

## Initial route map

| Route | Purpose |
| --- | --- |
| `/` | Overview dashboard |
| `/production` | Production volume and inspection throughput |
| `/defects` | Defect distribution and Pareto analysis |
| `/batches` | Batch quality grades and risk |
| `/predictions` | Predictive quality-risk analysis |
| `/alerts` | Alerts and recommendations |
| `/reports` | Report generation and exports |
| `/history` | Historical inspection records |
| `/data-management` | CSV/imported data management |
| `/settings` | Workspace and notification settings |

## Data entities

- `Batch`: production batch identity, line, quantity, status, and quality grade.
- `Inspection`: standardized inspection record received from upstream components.
- `Defect`: normalized defect taxonomy and counts per batch/inspection.
- `QualityPrediction`: risk score, model version, confidence, and recommended action.
- `Alert`: severity, source, status, and acknowledgement metadata.

## Dependency choices

Frontend versions are pinned to stable major versions in `frontend/package.json`:
React 18, Vite 5, TypeScript 5, Tailwind CSS 3, React Router 6, Recharts 2,
Lucide React, Axios, React Hook Form, and Zod.

Backend versions are pinned in `backend/requirements.txt`: Flask 3, Flask-CORS,
Flask-SQLAlchemy, Flask-Migrate, PyMySQL, Pandas, NumPy, scikit-learn, Joblib,
and Pytest. Pandas, NumPy, and scikit-learn use compatible release ranges to
support Python 3.15 wheels on Windows.

## Running locally

```powershell
cd component4\frontend
Copy-Item .env.example .env
npm install
npm run dev
```

The dashboard opens at `http://localhost:5173`. Set `VITE_API_BASE_URL` in `.env` when
the Flask API is not running at its default URL. Start the backend first; an unavailable
API is shown as an explicit connection error with a retry action.

Complete Windows PowerShell setup, API contracts, seed/reset commands, model training,
and testing instructions are in [backend/README.md](backend/README.md).
