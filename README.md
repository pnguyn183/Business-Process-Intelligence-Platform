# FlowOps Business Process Intelligence Platform

Feature-complete reference implementation based on `FlowOps Business Process Intelligence Platform.docx`.

## What Is Included

- FastAPI backend with JWT-style bearer auth, refresh and password reset, RBAC CRUD, organization CRUD, process edit/version/publish/archive, workflow state machine, full task actions, SLA policy and escalation, KPI, bottleneck analytics, notifications, recommendations, audit, reports, CSV export, and Prometheus metrics.
- React + TypeScript frontend with Executive KPI, BPMN-style process designer, workflow start, full task actions, SLA policy management, bottleneck analytics, recommendations, organization management, reports, role-permission administration, and audit log.
- Local demo data for Recruitment, Purchase Request, and IT Access Request processes.
- Docker Compose target stack with PostgreSQL, MongoDB, Redis, Kafka, Prometheus, and Grafana.
- GitHub Actions CI for backend integration tests and frontend production build.

## Running Locally

### Backend

```powershell
cd backend
python -m venv .venv
.\\.venv\\Scripts\\Activate.ps1
pip install -r requirements.txt
uvicorn app:app --reload --host 127.0.0.1 --port 8000
```

### Frontend

```powershell
cd frontend
npm install
npm run dev -- --host 127.0.0.1 --port 5173
```

Open `http://127.0.0.1:5173`.

Vite proxies `/api` and `/metrics` to the backend at port `8000`.

## Docker Stack

```powershell
docker compose up --build
```

- FlowOps: `http://127.0.0.1:5173`
- FastAPI docs: `http://127.0.0.1:8000/docs`
- Prometheus: `http://127.0.0.1:9090`
- Grafana: `http://127.0.0.1:3000` using `admin` / `flowops`

## Demo Accounts

All demo accounts use `FlowOps@123`.

- `admin@flowops.vn`
- `process.manager@flowops.vn`
- `department.manager@flowops.vn`
- `employee@flowops.vn`
- `executive@flowops.vn`

## Verification

```powershell
cd frontend
npm run build
```

```powershell
cd backend
.\\.venv\\Scripts\\python.exe -m pip install -r requirements-dev.txt
.\\.venv\\Scripts\\python.exe -m pytest -q
```

See [requirements traceability](docs/requirements-traceability.md) for the mapping from the DOCX requirements to code and UI.
