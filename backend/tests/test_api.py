from uuid import uuid4

from fastapi.testclient import TestClient

from app import app


client = TestClient(app)


def auth_headers() -> dict[str, str]:
    response = client.post(
        "/api/auth/login",
        json={"email": "admin@flowops.vn", "password": "FlowOps@123"},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_health_login_refresh_and_forgot_password() -> None:
    assert client.get("/api/health").json()["status"] == "ok"
    login = client.post(
        "/api/auth/login",
        json={"email": "admin@flowops.vn", "password": "FlowOps@123"},
    )
    assert login.status_code == 200
    session = login.json()
    refresh = client.post("/api/auth/refresh", json={"refresh_token": session["refresh_token"]})
    assert refresh.status_code == 200
    forgot = client.post("/api/auth/forgot-password", json={"email": "employee@flowops.vn"})
    assert forgot.status_code == 200
    assert forgot.json()["delivery"] == "email-simulated"


def test_rbac_and_organization_management() -> None:
    headers = auth_headers()
    suffix = uuid4().hex[:6]
    role = client.post(
        "/api/rbac/roles",
        headers=headers,
        json={"name": f"Quality Analyst {suffix}", "permissions": ["tasks.view", "analytics.view"]},
    )
    assert role.status_code == 201

    department = client.post(
        "/api/organization/departments",
        headers=headers,
        json={"name": f"Quality {suffix}"},
    )
    assert department.status_code == 201
    department_id = department.json()["id"]
    team = client.post(
        "/api/organization/teams",
        headers=headers,
        json={"name": f"QA Team {suffix}", "department_id": department_id},
    )
    position = client.post(
        "/api/organization/positions",
        headers=headers,
        json={"name": f"QA Specialist {suffix}", "department_id": department_id},
    )
    assert team.status_code == 201
    assert position.status_code == 201

    employee = client.post(
        "/api/organization/employees",
        headers=headers,
        json={
            "name": f"QA User {suffix}",
            "email": f"qa-{suffix}@flowops.vn",
            "role": role.json()["name"],
            "department_id": department_id,
            "team_id": team.json()["id"],
            "position_id": position.json()["id"],
        },
    )
    assert employee.status_code == 201
    manager = client.patch(
        f"/api/organization/departments/{department_id}/manager",
        headers=headers,
        json={"manager_id": employee.json()["id"]},
    )
    assert manager.status_code == 200


def test_process_version_workflow_and_task_state_machine() -> None:
    headers = auth_headers()
    suffix = uuid4().hex[:6]
    created = client.post(
        "/api/processes",
        headers=headers,
        json={
            "name": f"Test Fulfilment {suffix}",
            "description": "Integration test process for the workflow state machine.",
            "owner_department_id": "dept-it",
            "stages": [
                {"name": "Start", "type": "Start Event", "sla_days": 0},
                {"name": "Review", "type": "User Task", "sla_days": 1},
                {"name": "Fulfil", "type": "Service Task", "sla_days": 1},
                {"name": "End", "type": "End Event", "sla_days": 0},
            ],
        },
    )
    assert created.status_code == 201
    process_id = created.json()["id"]
    published = client.post(f"/api/processes/{process_id}/publish", headers=headers)
    assert published.status_code == 200
    assert published.json()["status"] == "Published"

    started = client.post(
        "/api/workflows/start",
        headers=headers,
        json={"process_id": process_id, "title": f"Integration run {suffix}"},
    )
    assert started.status_code == 201
    workflow_id = started.json()["id"]
    first_task_id = started.json()["task"]["id"]

    claimed = client.post(
        f"/api/tasks/{first_task_id}/actions",
        headers=headers,
        json={"action": "claim"},
    )
    assert claimed.status_code == 200
    assert claimed.json()["status"] == "In Progress"
    completed = client.post(
        f"/api/tasks/{first_task_id}/actions",
        headers=headers,
        json={"action": "complete"},
    )
    assert completed.status_code == 200

    workflow = client.get(f"/api/workflows/{workflow_id}", headers=headers).json()
    active = [task for task in workflow["tasks"] if task["status"] in {"Pending", "In Progress"}]
    assert len(active) == 1
    second = client.post(
        f"/api/tasks/{active[0]['id']}/actions",
        headers=headers,
        json={"action": "complete"},
    )
    assert second.status_code == 200
    final_workflow = client.get(f"/api/workflows/{workflow_id}", headers=headers).json()
    assert final_workflow["status"] == "Completed"

    version = client.post(f"/api/processes/{process_id}/version", headers=headers)
    assert version.status_code == 200
    assert version.json()["status"] == "Draft"


def test_sla_reports_and_metrics() -> None:
    headers = auth_headers()
    policies = client.get("/api/sla/policies", headers=headers)
    assert policies.status_code == 200
    assert policies.json()
    policy = policies.json()[0]
    updated = client.patch(
        f"/api/sla/policies/{policy['id']}",
        headers=headers,
        json={
            "process_id": policy["process_id"],
            "stage_id": policy["stage_id"],
            "target_hours": 36,
            "warning_percent": 75,
            "escalation_role": "Process Manager",
            "active": True,
        },
    )
    assert updated.status_code == 200
    assert updated.json()["warning_percent"] == 75
    scan = client.post("/api/sla/scan", headers=headers)
    assert scan.status_code == 200
    assert "escalated_count" in scan.json()

    report = client.get("/api/reports/summary", headers=headers)
    assert report.status_code == 200
    assert len(report.json()["objectives"]) == 5
    exported = client.get("/api/reports/export", headers=headers)
    assert exported.status_code == 200
    assert exported.headers["content-type"].startswith("text/csv")
    metrics = client.get("/metrics")
    assert metrics.status_code == 200
    assert "flowops_sla_compliance_ratio" in metrics.text
