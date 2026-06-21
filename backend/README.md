# FlowOps Backend

FastAPI reference backend for the FlowOps Business Process Intelligence Platform.

## Run

```powershell
cd backend
python -m venv .venv
.\\.venv\\Scripts\\Activate.ps1
pip install -r requirements.txt
uvicorn app:app --reload --port 8000
```

## Test

```powershell
pip install -r requirements-dev.txt
pytest -q
```

Demo users all use the password `FlowOps@123`.

- `admin@flowops.vn`
- `process.manager@flowops.vn`
- `department.manager@flowops.vn`
- `employee@flowops.vn`
- `executive@flowops.vn`
