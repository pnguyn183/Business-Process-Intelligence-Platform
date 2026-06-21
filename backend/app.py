from __future__ import annotations

import base64
import csv
import hashlib
import hmac
import io
import json
import time
from collections import defaultdict
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from statistics import mean
from typing import Any, Literal
from uuid import uuid4

from fastapi import Depends, FastAPI, HTTPException, Query, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse, StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field


app = FastAPI(
    title="FlowOps API",
    version="1.1.0",
    description="Business Process Intelligence Platform reference implementation",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

auth_scheme = HTTPBearer(auto_error=False)
SECRET = "flowops-local-demo-secret"
REVOKED_TOKENS: set[str] = set()
REQUEST_METRICS = {"count": 0, "errors": 0, "duration_seconds": 0.0}

NOW = datetime.now(timezone.utc)


@app.middleware("http")
async def collect_request_metrics(request: Request, call_next):
    started = time.perf_counter()
    REQUEST_METRICS["count"] += 1
    try:
        response = await call_next(request)
    except Exception:
        REQUEST_METRICS["errors"] += 1
        raise
    duration = time.perf_counter() - started
    REQUEST_METRICS["duration_seconds"] += duration
    if response.status_code >= 500:
        REQUEST_METRICS["errors"] += 1
    response.headers["X-Process-Time-Ms"] = f"{duration * 1000:.2f}"
    return response


def ago(days: float) -> datetime:
    return NOW - timedelta(days=days)


def ahead(days: float) -> datetime:
    return NOW + timedelta(days=days)


def b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def b64decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def make_token(user_id: str, token_type: Literal["access", "refresh"]) -> str:
    lifetime = timedelta(minutes=45) if token_type == "access" else timedelta(days=7)
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "sub": user_id,
        "type": token_type,
        "iat": int(datetime.now(timezone.utc).timestamp()),
        "exp": int((datetime.now(timezone.utc) + lifetime).timestamp()),
        "jti": str(uuid4()),
    }
    header_part = b64url(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    payload_part = b64url(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signing_input = f"{header_part}.{payload_part}".encode("ascii")
    signature = hmac.new(SECRET.encode("utf-8"), signing_input, hashlib.sha256).digest()
    return f"{header_part}.{payload_part}.{b64url(signature)}"


def verify_token(token: str, expected_type: Literal["access", "refresh"]) -> dict[str, Any]:
    if token in REVOKED_TOKENS:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token has been revoked")
    parts = token.split(".")
    if len(parts) != 3:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token")
    signing_input = f"{parts[0]}.{parts[1]}".encode("ascii")
    expected_signature = hmac.new(SECRET.encode("utf-8"), signing_input, hashlib.sha256).digest()
    try:
        actual_signature = b64decode(parts[2])
        payload = json.loads(b64decode(parts[1]))
    except (ValueError, json.JSONDecodeError):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token") from None
    if not hmac.compare_digest(actual_signature, expected_signature):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token signature")
    if payload.get("type") != expected_type:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token type")
    if payload.get("exp", 0) < int(datetime.now(timezone.utc).timestamp()):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token expired")
    return payload


def require_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(auth_scheme),
) -> dict[str, Any]:
    if credentials is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing bearer token")
    payload = verify_token(credentials.credentials, "access")
    user = USERS_BY_ID.get(payload["sub"])
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User not found")
    return user


class LoginRequest(BaseModel):
    email: str
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class ForgotPasswordRequest(BaseModel):
    email: str


class ResetPasswordRequest(BaseModel):
    reset_token: str
    new_password: str = Field(min_length=8)


class StageDefinition(BaseModel):
    name: str = Field(min_length=2)
    type: Literal[
        "Start Event",
        "End Event",
        "Task",
        "User Task",
        "Service Task",
        "Gateway",
        "Parallel Gateway",
        "Sequence Flow",
    ] = "User Task"
    sla_days: float = Field(default=2, ge=0)


class ProcessCreate(BaseModel):
    name: str = Field(min_length=3)
    description: str = Field(min_length=3)
    owner_department_id: str
    stages: list[str | StageDefinition] = Field(min_length=2)


class ProcessUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=3)
    description: str | None = Field(default=None, min_length=3)
    owner_department_id: str | None = None
    stages: list[str | StageDefinition] | None = Field(default=None, min_length=2)


class WorkflowStart(BaseModel):
    process_id: str
    title: str = Field(min_length=3)
    requester_id: str | None = None


class TaskPatch(BaseModel):
    status: Literal["Pending", "In Progress", "Completed", "Rejected", "Cancelled"] | None = None
    assignee_id: str | None = None
    priority: Literal["Low", "Medium", "High", "Critical"] | None = None


class RolePayload(BaseModel):
    name: str = Field(min_length=2)
    permissions: list[str] = Field(default_factory=list)


class DepartmentPayload(BaseModel):
    name: str = Field(min_length=2)
    manager_id: str | None = None


class TeamPayload(BaseModel):
    name: str = Field(min_length=2)
    department_id: str


class PositionPayload(BaseModel):
    name: str = Field(min_length=2)
    department_id: str


class EmployeePayload(BaseModel):
    name: str = Field(min_length=2)
    email: str
    role: str
    department_id: str
    team_id: str
    position_id: str


class ManagerAssignment(BaseModel):
    manager_id: str


class WorkflowAction(BaseModel):
    action: Literal["move", "reject", "complete", "cancel", "escalate"]
    target_stage_id: str | None = None
    reason: str | None = None


class TaskAction(BaseModel):
    action: Literal["claim", "assign", "reassign", "start", "complete", "reject", "cancel", "escalate"]
    assignee_id: str | None = None
    reason: str | None = None


class SlaPolicyPayload(BaseModel):
    process_id: str
    stage_id: str
    target_hours: float = Field(gt=0)
    warning_percent: int = Field(default=80, ge=1, le=100)
    escalation_role: str = "Manager"
    active: bool = True


class NotificationPayload(BaseModel):
    type: str = Field(min_length=2)
    title: str = Field(min_length=2)
    message: str = Field(min_length=2)
    recipient_id: str | None = None


ROLES = [
    {
        "id": "role-admin",
        "name": "Admin",
        "permissions": [
            "auth.manage",
            "organization.manage",
            "process.manage",
            "workflow.execute",
            "analytics.view",
            "notifications.manage",
        ],
    },
    {
        "id": "role-process-manager",
        "name": "Process Manager",
        "permissions": ["process.manage", "workflow.execute", "analytics.view"],
    },
    {
        "id": "role-manager",
        "name": "Manager",
        "permissions": ["workflow.execute", "tasks.assign", "analytics.department.view"],
    },
    {
        "id": "role-employee",
        "name": "Employee",
        "permissions": ["tasks.view", "tasks.complete"],
    },
    {
        "id": "role-executive",
        "name": "Executive Management",
        "permissions": ["analytics.view", "reports.view"],
    },
]

ALL_PERMISSIONS = [
    "auth.manage",
    "organization.manage",
    "process.manage",
    "workflow.execute",
    "tasks.view",
    "tasks.assign",
    "tasks.complete",
    "sla.manage",
    "analytics.view",
    "analytics.department.view",
    "notifications.manage",
    "reports.view",
]

DEPARTMENTS = [
    {"id": "dept-hr", "name": "Human Resources", "manager_id": "emp-linh"},
    {"id": "dept-procurement", "name": "Procurement", "manager_id": "emp-minh"},
    {"id": "dept-finance", "name": "Finance", "manager_id": "emp-anh"},
    {"id": "dept-it", "name": "Information Technology", "manager_id": "emp-khoa"},
]

TEAMS = [
    {"id": "team-talent", "name": "Talent Acquisition", "department_id": "dept-hr"},
    {"id": "team-peopleops", "name": "People Operations", "department_id": "dept-hr"},
    {"id": "team-buying", "name": "Buying Desk", "department_id": "dept-procurement"},
    {"id": "team-ap", "name": "Accounts Payable", "department_id": "dept-finance"},
    {"id": "team-platform", "name": "Platform Operations", "department_id": "dept-it"},
]

POSITIONS = [
    {"id": "pos-admin", "name": "System Administrator", "department_id": "dept-it"},
    {"id": "pos-pm", "name": "Process Excellence Lead", "department_id": "dept-it"},
    {"id": "pos-manager", "name": "Department Manager", "department_id": "dept-hr"},
    {"id": "pos-employee", "name": "Operations Specialist", "department_id": "dept-hr"},
    {"id": "pos-executive", "name": "Chief Operating Officer", "department_id": "dept-finance"},
]

EMPLOYEES = [
    {
        "id": "emp-khoa",
        "name": "Khoa Tran",
        "email": "admin@flowops.vn",
        "role": "Admin",
        "department_id": "dept-it",
        "team_id": "team-platform",
        "position_id": "pos-admin",
    },
    {
        "id": "emp-phuc",
        "name": "Phuc Nguyen",
        "email": "process.manager@flowops.vn",
        "role": "Process Manager",
        "department_id": "dept-it",
        "team_id": "team-platform",
        "position_id": "pos-pm",
    },
    {
        "id": "emp-linh",
        "name": "Linh Hoang",
        "email": "department.manager@flowops.vn",
        "role": "Manager",
        "department_id": "dept-hr",
        "team_id": "team-talent",
        "position_id": "pos-manager",
    },
    {
        "id": "emp-mai",
        "name": "Mai Le",
        "email": "employee@flowops.vn",
        "role": "Employee",
        "department_id": "dept-hr",
        "team_id": "team-talent",
        "position_id": "pos-employee",
    },
    {
        "id": "emp-anh",
        "name": "Anh Vo",
        "email": "executive@flowops.vn",
        "role": "Executive Management",
        "department_id": "dept-finance",
        "team_id": "team-ap",
        "position_id": "pos-executive",
    },
    {
        "id": "emp-minh",
        "name": "Minh Do",
        "email": "minh.procurement@flowops.vn",
        "role": "Manager",
        "department_id": "dept-procurement",
        "team_id": "team-buying",
        "position_id": "pos-manager",
    },
]

USERS_BY_EMAIL = {
    employee["email"]: {
        "id": employee["id"],
        "name": employee["name"],
        "email": employee["email"],
        "role": employee["role"],
        "department_id": employee["department_id"],
        "password": "FlowOps@123",
    }
    for employee in EMPLOYEES
}
USERS_BY_ID = {user["id"]: user for user in USERS_BY_EMAIL.values()}

PROCESSES: list[dict[str, Any]] = [
    {
        "id": "proc-recruitment",
        "name": "Recruitment Process",
        "description": "Apply, CV screening, interview, offer, and onboarding flow.",
        "status": "Published",
        "version": 3,
        "owner_department_id": "dept-hr",
        "created_by": "emp-phuc",
        "created_at": ago(31),
        "stages": [
            {"id": "stage-apply", "name": "Apply", "type": "Start Event", "sla_days": 0.5},
            {"id": "stage-screen", "name": "CV Screening", "type": "User Task", "sla_days": 2},
            {"id": "stage-interview", "name": "Interview", "type": "User Task", "sla_days": 3},
            {"id": "stage-offer", "name": "Offer Approval", "type": "Gateway", "sla_days": 2},
            {"id": "stage-onboarding", "name": "Onboarding", "type": "End Event", "sla_days": 5},
        ],
    },
    {
        "id": "proc-purchase",
        "name": "Purchase Request",
        "description": "Purchase request, manager approval, procurement approval, and PO creation.",
        "status": "Published",
        "version": 2,
        "owner_department_id": "dept-procurement",
        "created_by": "emp-phuc",
        "created_at": ago(24),
        "stages": [
            {"id": "stage-create", "name": "Create Request", "type": "Start Event", "sla_days": 1},
            {"id": "stage-manager", "name": "Manager Approval", "type": "User Task", "sla_days": 2},
            {"id": "stage-procurement", "name": "Procurement Approval", "type": "User Task", "sla_days": 3},
            {"id": "stage-po", "name": "Purchase Order", "type": "Service Task", "sla_days": 2},
            {"id": "stage-end", "name": "End", "type": "End Event", "sla_days": 0},
        ],
    },
    {
        "id": "proc-access",
        "name": "IT Access Request",
        "description": "New access request, manager approval, provisioning, and audit confirmation.",
        "status": "Draft",
        "version": 1,
        "owner_department_id": "dept-it",
        "created_by": "emp-khoa",
        "created_at": ago(6),
        "stages": [
            {"id": "stage-request", "name": "Create Access Request", "type": "Start Event", "sla_days": 0.5},
            {"id": "stage-approve", "name": "Manager Approval", "type": "User Task", "sla_days": 1},
            {"id": "stage-provision", "name": "Provision Account", "type": "Service Task", "sla_days": 1},
            {"id": "stage-audit", "name": "Audit Confirmation", "type": "End Event", "sla_days": 1},
        ],
    },
]

WORKFLOWS: list[dict[str, Any]] = [
    {
        "id": "wf-1001",
        "process_id": "proc-recruitment",
        "title": "Senior Backend Engineer Hiring",
        "requester_id": "emp-linh",
        "status": "In Progress",
        "current_stage": "Interview",
        "started_at": ago(10),
        "completed_at": None,
    },
    {
        "id": "wf-1002",
        "process_id": "proc-purchase",
        "title": "Laptop Batch for Sales Team",
        "requester_id": "emp-minh",
        "status": "Completed",
        "current_stage": "End",
        "started_at": ago(8),
        "completed_at": ago(2),
    },
    {
        "id": "wf-1003",
        "process_id": "proc-recruitment",
        "title": "Data Analyst Hiring",
        "requester_id": "emp-linh",
        "status": "Pending",
        "current_stage": "CV Screening",
        "started_at": ago(4),
        "completed_at": None,
    },
    {
        "id": "wf-1004",
        "process_id": "proc-purchase",
        "title": "Data Warehouse License",
        "requester_id": "emp-anh",
        "status": "In Progress",
        "current_stage": "Procurement Approval",
        "started_at": ago(5),
        "completed_at": None,
    },
]

TASKS: list[dict[str, Any]] = [
    {
        "id": "task-2001",
        "workflow_id": "wf-1001",
        "process_id": "proc-recruitment",
        "stage_id": "stage-screen",
        "name": "Screen backend engineer CVs",
        "assignee_id": "emp-mai",
        "department_id": "dept-hr",
        "priority": "High",
        "status": "Completed",
        "created_at": ago(9),
        "due_at": ago(7),
        "completed_at": ago(7.4),
    },
    {
        "id": "task-2002",
        "workflow_id": "wf-1001",
        "process_id": "proc-recruitment",
        "stage_id": "stage-interview",
        "name": "Coordinate technical interviews",
        "assignee_id": "emp-linh",
        "department_id": "dept-hr",
        "priority": "Critical",
        "status": "In Progress",
        "created_at": ago(6),
        "due_at": ago(3),
        "completed_at": None,
    },
    {
        "id": "task-2003",
        "workflow_id": "wf-1002",
        "process_id": "proc-purchase",
        "stage_id": "stage-manager",
        "name": "Approve laptop purchase",
        "assignee_id": "emp-minh",
        "department_id": "dept-procurement",
        "priority": "Medium",
        "status": "Completed",
        "created_at": ago(7),
        "due_at": ago(5),
        "completed_at": ago(5.2),
    },
    {
        "id": "task-2004",
        "workflow_id": "wf-1002",
        "process_id": "proc-purchase",
        "stage_id": "stage-po",
        "name": "Create purchase order",
        "assignee_id": "emp-minh",
        "department_id": "dept-procurement",
        "priority": "Medium",
        "status": "Completed",
        "created_at": ago(4),
        "due_at": ago(2),
        "completed_at": ago(2.1),
    },
    {
        "id": "task-2005",
        "workflow_id": "wf-1003",
        "process_id": "proc-recruitment",
        "stage_id": "stage-screen",
        "name": "Screen data analyst CVs",
        "assignee_id": "emp-mai",
        "department_id": "dept-hr",
        "priority": "High",
        "status": "Pending",
        "created_at": ago(4),
        "due_at": ago(2),
        "completed_at": None,
    },
    {
        "id": "task-2006",
        "workflow_id": "wf-1004",
        "process_id": "proc-purchase",
        "stage_id": "stage-procurement",
        "name": "Review data warehouse vendor quote",
        "assignee_id": "emp-minh",
        "department_id": "dept-procurement",
        "priority": "Critical",
        "status": "In Progress",
        "created_at": ago(2.5),
        "due_at": ahead(0.5),
        "completed_at": None,
    },
    {
        "id": "task-2007",
        "workflow_id": "wf-1004",
        "process_id": "proc-purchase",
        "stage_id": "stage-manager",
        "name": "Finance budget check",
        "assignee_id": "emp-anh",
        "department_id": "dept-finance",
        "priority": "High",
        "status": "Completed",
        "created_at": ago(4),
        "due_at": ago(2),
        "completed_at": ago(1.6),
    },
]

NOTIFICATIONS: list[dict[str, Any]] = [
    {
        "id": "notif-1",
        "type": "SLA Violation",
        "title": "Interview task breached SLA",
        "message": "Senior Backend Engineer Hiring is 3 days past target.",
        "recipient_id": "emp-linh",
        "created_at": ago(0.2),
        "read": False,
    },
    {
        "id": "notif-2",
        "type": "Task Due Soon",
        "title": "Vendor quote review due soon",
        "message": "Data Warehouse License procurement review is due within 12 hours.",
        "recipient_id": "emp-minh",
        "created_at": ago(0.35),
        "read": False,
    },
    {
        "id": "notif-3",
        "type": "Process Completed",
        "title": "Purchase request completed",
        "message": "Laptop Batch for Sales Team was completed successfully.",
        "recipient_id": "emp-anh",
        "created_at": ago(2),
        "read": True,
    },
]

AUDIT_LOG: list[dict[str, Any]] = [
    {"id": "audit-1", "actor_id": "emp-phuc", "action": "Published Recruitment Process v3", "created_at": ago(5)},
    {"id": "audit-2", "actor_id": "emp-linh", "action": "Assigned Interview task to HR Manager", "created_at": ago(4)},
    {"id": "audit-3", "actor_id": "emp-minh", "action": "Completed purchase order creation", "created_at": ago(2)},
]

PASSWORD_RESET_TOKENS: dict[str, dict[str, Any]] = {}
PROCESS_VERSIONS: list[dict[str, Any]] = [
    {
        "id": f"version-{process['id']}-{process['version']}",
        "process_id": process["id"],
        "version": process["version"],
        "status": process["status"],
        "snapshot": deepcopy(process),
        "created_at": process["created_at"],
        "created_by": process["created_by"],
    }
    for process in PROCESSES
]
SLA_POLICIES: list[dict[str, Any]] = [
    {
        "id": f"sla-{stage['id']}",
        "process_id": process["id"],
        "process_name": process["name"],
        "stage_id": stage["id"],
        "stage_name": stage["name"],
        "target_hours": max(stage["sla_days"] * 24, 1),
        "warning_percent": 80,
        "escalation_role": "Manager",
        "active": True,
    }
    for process in PROCESSES
    for stage in process["stages"]
    if stage["type"] in {"Task", "User Task", "Service Task"}
]


def department_name(department_id: str) -> str:
    return next((department["name"] for department in DEPARTMENTS if department["id"] == department_id), "Unknown")


def employee_name(employee_id: str | None) -> str:
    return next((employee["name"] for employee in EMPLOYEES if employee["id"] == employee_id), "Unassigned")


def process_name(process_id: str) -> str:
    return next((process["name"] for process in PROCESSES if process["id"] == process_id), "Unknown Process")


def get_process(process_id: str) -> dict[str, Any]:
    process = next((item for item in PROCESSES if item["id"] == process_id), None)
    if not process:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Process not found")
    return process


def get_task(task_id: str) -> dict[str, Any]:
    task = next((item for item in TASKS if item["id"] == task_id), None)
    if not task:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Task not found")
    return task


def get_workflow(workflow_id: str) -> dict[str, Any]:
    workflow = next((item for item in WORKFLOWS if item["id"] == workflow_id), None)
    if not workflow:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Workflow not found")
    return workflow


def get_employee(employee_id: str) -> dict[str, Any]:
    employee = next((item for item in EMPLOYEES if item["id"] == employee_id), None)
    if not employee:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Employee not found")
    return employee


def require_permission(permission: str):
    def dependency(user: dict[str, Any] = Depends(require_user)) -> dict[str, Any]:
        if user["role"] == "Admin":
            return user
        role = next((item for item in ROLES if item["name"] == user["role"]), None)
        if not role or permission not in role["permissions"]:
            raise HTTPException(status.HTTP_403_FORBIDDEN, f"Missing permission: {permission}")
        return user

    return dependency


def record_audit(actor_id: str, action: str, entity_type: str = "system", entity_id: str | None = None) -> None:
    AUDIT_LOG.append(
        {
            "id": f"audit-{uuid4().hex[:10]}",
            "actor_id": actor_id,
            "action": action,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "created_at": datetime.now(timezone.utc),
        }
    )


def add_notification(
    notification_type: str,
    title: str,
    message: str,
    recipient_id: str | None,
) -> dict[str, Any]:
    notification = {
        "id": f"notif-{uuid4().hex[:10]}",
        "type": notification_type,
        "title": title,
        "message": message,
        "recipient_id": recipient_id,
        "created_at": datetime.now(timezone.utc),
        "read": False,
    }
    NOTIFICATIONS.append(notification)
    return notification


def normalize_stages(stages: list[str | StageDefinition]) -> list[dict[str, Any]]:
    normalized = []
    for index, stage in enumerate(stages):
        if isinstance(stage, str):
            stage_type = "User Task"
            if index == 0:
                stage_type = "Start Event"
            elif index == len(stages) - 1:
                stage_type = "End Event"
            normalized.append(
                {
                    "id": f"stage-{uuid4().hex[:8]}",
                    "name": stage,
                    "type": stage_type,
                    "sla_days": 0 if stage_type in {"Start Event", "End Event"} else 2,
                }
            )
        else:
            normalized.append({"id": f"stage-{uuid4().hex[:8]}", **stage.model_dump()})
    if normalized[0]["type"] != "Start Event" or normalized[-1]["type"] != "End Event":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "A process must start with Start Event and end with End Event")
    return normalized


def enrich_workflow(workflow: dict[str, Any]) -> dict[str, Any]:
    return {
        **workflow,
        "process_name": process_name(workflow["process_id"]),
        "requester_name": employee_name(workflow["requester_id"]),
        "cycle_time_days": workflow_cycle_days(workflow),
        "tasks": [enrich_task(task) for task in TASKS if task["workflow_id"] == workflow["id"]],
    }


def create_stage_task(workflow: dict[str, Any], process: dict[str, Any], stage: dict[str, Any]) -> dict[str, Any]:
    assignee_id = next(
        (employee["id"] for employee in EMPLOYEES if employee["department_id"] == process["owner_department_id"]),
        None,
    )
    now = datetime.now(timezone.utc)
    policy = next(
        (item for item in SLA_POLICIES if item["stage_id"] == stage["id"] and item["active"]),
        None,
    )
    target_hours = policy["target_hours"] if policy else max(stage.get("sla_days", 1) * 24, 1)
    task = {
        "id": f"task-{uuid4().hex[:8]}",
        "workflow_id": workflow["id"],
        "process_id": process["id"],
        "stage_id": stage["id"],
        "name": stage["name"],
        "assignee_id": assignee_id,
        "department_id": process["owner_department_id"],
        "priority": "Medium",
        "status": "Pending",
        "created_at": now,
        "due_at": now + timedelta(hours=target_hours),
        "completed_at": None,
        "escalation_count": 0,
    }
    TASKS.append(task)
    add_notification(
        "Task Assigned",
        f"{stage['name']} assigned",
        f"{workflow['title']} is ready for {employee_name(assignee_id)}.",
        assignee_id,
    )
    return task


def advance_workflow(workflow: dict[str, Any], completed_task: dict[str, Any]) -> dict[str, Any] | None:
    process = get_process(workflow["process_id"])
    current_index = next(
        (index for index, stage in enumerate(process["stages"]) if stage["id"] == completed_task["stage_id"]),
        -1,
    )
    for stage in process["stages"][current_index + 1 :]:
        workflow["current_stage"] = stage["name"]
        if stage["type"] == "End Event":
            workflow["status"] = "Completed"
            workflow["completed_at"] = datetime.now(timezone.utc)
            add_notification("Process Completed", workflow["title"], f"{workflow['title']} completed successfully.", workflow["requester_id"])
            return None
        if stage["type"] in {"Task", "User Task", "Service Task"}:
            workflow["status"] = "In Progress"
            return create_stage_task(workflow, process, stage)
    workflow["status"] = "Completed"
    workflow["completed_at"] = datetime.now(timezone.utc)
    return None


def perform_task_action(task: dict[str, Any], payload: TaskAction, user: dict[str, Any]) -> dict[str, Any]:
    if task["status"] in {"Completed", "Rejected", "Cancelled"}:
        raise HTTPException(status.HTTP_409_CONFLICT, "Task is already in a terminal state")
    workflow = get_workflow(task["workflow_id"])

    if payload.action == "claim":
        task["assignee_id"] = user["id"]
        task["status"] = "In Progress"
    elif payload.action in {"assign", "reassign"}:
        if not payload.assignee_id:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "assignee_id is required")
        get_employee(payload.assignee_id)
        task["assignee_id"] = payload.assignee_id
        add_notification("Task Assigned", task["name"], f"{task['name']} was assigned to you.", payload.assignee_id)
    elif payload.action == "start":
        task["status"] = "In Progress"
        workflow["status"] = "In Progress"
    elif payload.action == "complete":
        task["status"] = "Completed"
        task["completed_at"] = datetime.now(timezone.utc)
        advance_workflow(workflow, task)
    elif payload.action == "reject":
        task["status"] = "Rejected"
        task["completed_at"] = datetime.now(timezone.utc)
        workflow["status"] = "Rejected"
        workflow["completed_at"] = datetime.now(timezone.utc)
    elif payload.action == "cancel":
        task["status"] = "Cancelled"
        task["completed_at"] = datetime.now(timezone.utc)
        workflow["status"] = "Cancelled"
        workflow["completed_at"] = datetime.now(timezone.utc)
    elif payload.action == "escalate":
        task["priority"] = "Critical"
        task["escalation_count"] = task.get("escalation_count", 0) + 1
        manager_id = next(
            (department["manager_id"] for department in DEPARTMENTS if department["id"] == task["department_id"]),
            None,
        )
        add_notification(
            "Task Escalated",
            task["name"],
            payload.reason or f"{task['name']} requires management attention.",
            manager_id,
        )

    record_audit(user["id"], f"{payload.action.title()} task {task['name']}", "task", task["id"])
    return enrich_task(task)


def task_sla(task: dict[str, Any]) -> dict[str, Any]:
    completed_at = task.get("completed_at")
    due_at = task["due_at"]
    end = completed_at or datetime.now(timezone.utc)
    total_seconds = max((due_at - task["created_at"]).total_seconds(), 1)
    consumed = max((end - task["created_at"]).total_seconds(), 0)
    consumed_ratio = min(consumed / total_seconds, 1.25)
    policy = next(
        (item for item in SLA_POLICIES if item["stage_id"] == task["stage_id"] and item["active"]),
        None,
    )
    warning_ratio = (policy["warning_percent"] / 100) if policy else 0.8
    if completed_at:
        status_label = "Green" if completed_at <= due_at else "Red"
    elif end > due_at:
        status_label = "Red"
    elif consumed_ratio >= warning_ratio:
        status_label = "Yellow"
    else:
        status_label = "Green"
    remaining_hours = round((due_at - datetime.now(timezone.utc)).total_seconds() / 3600, 1)
    return {
        "status": status_label,
        "consumed_percent": round(min(consumed_ratio, 1) * 100, 1),
        "remaining_hours": remaining_hours,
        "breached": status_label == "Red",
    }


def enrich_task(task: dict[str, Any]) -> dict[str, Any]:
    return {
        **task,
        "assignee_name": employee_name(task.get("assignee_id")),
        "department_name": department_name(task["department_id"]),
        "process_name": process_name(task["process_id"]),
        "sla": task_sla(task),
    }


def workflow_cycle_days(workflow: dict[str, Any]) -> float:
    end = workflow["completed_at"] or datetime.now(timezone.utc)
    return round((end - workflow["started_at"]).total_seconds() / 86400, 1)


def build_executive_metrics() -> dict[str, Any]:
    enriched = [enrich_task(task) for task in TASKS]
    completed_tasks = [task for task in TASKS if task["status"] == "Completed" and task["completed_at"]]
    compliant_count = sum(1 for task in enriched if task["sla"]["status"] == "Green")
    delayed_instances = {
        task["workflow_id"]
        for task in enriched
        if task["sla"]["status"] == "Red" and task["status"] != "Completed"
    }
    average_task_time = (
        mean(
            (task["completed_at"] - task["created_at"]).total_seconds() / 86400
            for task in completed_tasks
        )
        if completed_tasks
        else 0
    )
    return {
        "process_count": len(PROCESSES),
        "running_processes": sum(1 for item in WORKFLOWS if item["status"] in {"Pending", "In Progress"}),
        "completed_processes": sum(1 for item in WORKFLOWS if item["status"] == "Completed"),
        "delayed_processes": len(delayed_instances),
        "average_processing_time_days": round(average_task_time, 1),
        "sla_compliance_rate": round((compliant_count / max(len(enriched), 1)) * 100, 1),
    }


def build_department_metrics() -> list[dict[str, Any]]:
    rows = []
    for department in DEPARTMENTS:
        department_tasks = [task for task in TASKS if task["department_id"] == department["id"]]
        completed = [task for task in department_tasks if task["status"] == "Completed" and task["completed_at"]]
        average_days = (
            mean((task["completed_at"] - task["created_at"]).total_seconds() / 86400 for task in completed)
            if completed
            else 0
        )
        compliant = sum(1 for task in department_tasks if task_sla(task)["status"] == "Green")
        rows.append(
            {
                "department_id": department["id"],
                "department": department["name"],
                "throughput": len(completed),
                "average_task_time_days": round(average_days, 1),
                "employee_productivity": round((len(completed) / max(len(department_tasks), 1)) * 100, 1),
                "process_success_rate": round((compliant / max(len(department_tasks), 1)) * 100, 1),
            }
        )
    return rows


def build_employee_metrics() -> list[dict[str, Any]]:
    rows = []
    for employee in EMPLOYEES:
        tasks = [task for task in TASKS if task["assignee_id"] == employee["id"]]
        completed = [task for task in tasks if task["status"] == "Completed" and task["completed_at"]]
        overdue = [task for task in tasks if task_sla(task)["status"] == "Red" and task["status"] != "Completed"]
        average_days = (
            mean((task["completed_at"] - task["created_at"]).total_seconds() / 86400 for task in completed)
            if completed
            else 0
        )
        rows.append(
            {
                "employee_id": employee["id"],
                "employee": employee["name"],
                "department": department_name(employee["department_id"]),
                "assigned_tasks": len(tasks),
                "completed_tasks": len(completed),
                "overdue_tasks": len(overdue),
                "average_completion_time_days": round(average_days, 1),
            }
        )
    return rows


def build_bottlenecks() -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for task in TASKS:
        grouped[(task["process_id"], task["stage_id"])].append(task)

    rows = []
    for (process_id, stage_id), tasks in grouped.items():
        process = get_process(process_id)
        stage = next((item for item in process["stages"] if item["id"] == stage_id), None)
        if not stage:
            continue
        waiting_days = [
            ((task.get("completed_at") or datetime.now(timezone.utc)) - task["created_at"]).total_seconds() / 86400
            for task in tasks
        ]
        delayed = sum(1 for task in tasks if task_sla(task)["status"] == "Red")
        delay_rate = round((delayed / max(len(tasks), 1)) * 100, 1)
        avg_waiting = round(mean(waiting_days), 1)
        if "Interview" in stage["name"]:
            root_cause = "Insufficient interviewers"
        elif delay_rate >= 50:
            root_cause = "Queue ownership is unclear"
        elif avg_waiting > stage["sla_days"]:
            root_cause = "Approval handoff takes too long"
        else:
            root_cause = "Within expected operating range"
        rows.append(
            {
                "process_id": process_id,
                "process": process["name"],
                "stage": stage["name"],
                "average_waiting_days": avg_waiting,
                "total_delays_percent": delay_rate,
                "cycle_time_days": round(avg_waiting + 0.7, 1),
                "lead_time_days": round(avg_waiting + 1.2, 1),
                "queue_time_days": avg_waiting,
                "throughput": sum(1 for task in tasks if task["status"] == "Completed"),
                "idle_time_days": round(max(avg_waiting - stage["sla_days"], 0), 1),
                "root_cause": root_cause,
                "severity": "High" if delay_rate >= 50 else "Medium" if delay_rate >= 25 else "Low",
            }
        )
    return sorted(rows, key=lambda item: (item["severity"] != "High", -item["total_delays_percent"]))


def build_recommendations() -> list[dict[str, Any]]:
    bottlenecks = build_bottlenecks()
    department_rows = build_department_metrics()
    employee_rows = build_employee_metrics()
    recommendations = []

    for bottleneck in bottlenecks:
        if bottleneck["total_delays_percent"] > 30:
            recommendations.append(
                {
                    "id": f"rec-sla-{bottleneck['process_id']}-{bottleneck['stage']}",
                    "type": "SLA",
                    "priority": "High",
                    "rule": "SLA Violation > 30%",
                    "recommendation": f"Increase reviewers for {bottleneck['stage']} in {bottleneck['process']}.",
                    "impact": "Expected to reduce delayed processes by 15-20%.",
                }
            )
        if bottleneck["queue_time_days"] > 5:
            recommendations.append(
                {
                    "id": f"rec-queue-{bottleneck['process_id']}-{bottleneck['stage']}",
                    "type": "Bottleneck",
                    "priority": "Medium",
                    "rule": "Queue Time > 5 days",
                    "recommendation": f"Parallelize approval flow around {bottleneck['stage']}.",
                    "impact": "Shortens cycle time for long-running workflow instances.",
                }
            )

    for employee in employee_rows:
        workload = employee["assigned_tasks"] * 20
        if workload > 80:
            recommendations.append(
                {
                    "id": f"rec-workload-{employee['employee_id']}",
                    "type": "Workload",
                    "priority": "Medium",
                    "rule": "Employee Workload > 80%",
                    "recommendation": f"Reassign tasks from {employee['employee']} to a lower-load teammate.",
                    "impact": "Balances work before SLA thresholds are breached.",
                }
            )

    if not recommendations:
        worst_department = min(department_rows, key=lambda item: item["process_success_rate"])
        recommendations.append(
            {
                "id": "rec-standardize-sla-review",
                "type": "KPI",
                "priority": "Low",
                "rule": "Lowest process success rate",
                "recommendation": f"Review SLA targets and handoff rules in {worst_department['department']}.",
                "impact": "Improves process visibility and accountability.",
            }
        )
    return recommendations[:8]


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "flowops-api"}


@app.post("/api/auth/login")
def login(payload: LoginRequest) -> dict[str, Any]:
    user = USERS_BY_EMAIL.get(payload.email.lower())
    if not user or user["password"] != payload.password:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password")
    access_token = make_token(user["id"], "access")
    refresh_token = make_token(user["id"], "refresh")
    safe_user = {key: value for key, value in user.items() if key != "password"}
    AUDIT_LOG.append(
        {"id": f"audit-{uuid4()}", "actor_id": user["id"], "action": "Logged in", "created_at": datetime.now(timezone.utc)}
    )
    return {"access_token": access_token, "refresh_token": refresh_token, "token_type": "bearer", "user": safe_user}


@app.post("/api/auth/refresh")
def refresh(payload: RefreshRequest) -> dict[str, str]:
    token_payload = verify_token(payload.refresh_token, "refresh")
    return {"access_token": make_token(token_payload["sub"], "access"), "token_type": "bearer"}


@app.post("/api/auth/logout")
def logout(
    payload: RefreshRequest,
    credentials: HTTPAuthorizationCredentials | None = Depends(auth_scheme),
) -> dict[str, str]:
    if credentials:
        REVOKED_TOKENS.add(credentials.credentials)
    REVOKED_TOKENS.add(payload.refresh_token)
    return {"status": "logged_out"}


@app.get("/api/auth/me")
def me(user: dict[str, Any] = Depends(require_user)) -> dict[str, Any]:
    return {key: value for key, value in user.items() if key != "password"}


@app.get("/api/rbac")
def rbac(_: dict[str, Any] = Depends(require_user)) -> dict[str, Any]:
    return {"roles": ROLES, "permissions": ALL_PERMISSIONS}


@app.get("/api/organization")
def organization(_: dict[str, Any] = Depends(require_user)) -> dict[str, Any]:
    employees = [
        {
            **employee,
            "department_name": department_name(employee["department_id"]),
            "manager_name": employee_name(
                next(
                    (department["manager_id"] for department in DEPARTMENTS if department["id"] == employee["department_id"]),
                    None,
                )
            ),
        }
        for employee in EMPLOYEES
    ]
    return {"departments": DEPARTMENTS, "teams": TEAMS, "positions": POSITIONS, "employees": employees}


@app.get("/api/processes")
def processes(_: dict[str, Any] = Depends(require_user)) -> list[dict[str, Any]]:
    return [
        {
            **process,
            "owner_department": department_name(process["owner_department_id"]),
            "instance_count": sum(1 for workflow in WORKFLOWS if workflow["process_id"] == process["id"]),
        }
        for process in PROCESSES
    ]


@app.post("/api/processes", status_code=status.HTTP_201_CREATED)
def create_process(payload: ProcessCreate, user: dict[str, Any] = Depends(require_permission("process.manage"))) -> dict[str, Any]:
    if not any(department["id"] == payload.owner_department_id for department in DEPARTMENTS):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Department does not exist")
    process = {
        "id": f"proc-{uuid4().hex[:8]}",
        "name": payload.name,
        "description": payload.description,
        "status": "Draft",
        "version": 1,
        "owner_department_id": payload.owner_department_id,
        "created_by": user["id"],
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
        "stages": normalize_stages(payload.stages),
    }
    PROCESSES.append(process)
    record_audit(user["id"], f"Created process {payload.name}", "process", process["id"])
    return {**process, "owner_department": department_name(process["owner_department_id"]), "instance_count": 0}


@app.post("/api/processes/{process_id}/publish")
def publish_process(process_id: str, user: dict[str, Any] = Depends(require_permission("process.manage"))) -> dict[str, Any]:
    process = get_process(process_id)
    if process["status"] == "Archived":
        raise HTTPException(status.HTTP_409_CONFLICT, "Archived processes cannot be published")
    existing_versions = [version for version in PROCESS_VERSIONS if version["process_id"] == process_id]
    if existing_versions and process["status"] == "Draft":
        process["version"] = max(version["version"] for version in existing_versions) + 1
    process["status"] = "Published"
    process["updated_at"] = datetime.now(timezone.utc)
    version_record = {
        "id": f"version-{process_id}-{process['version']}",
        "process_id": process_id,
        "version": process["version"],
        "status": "Published",
        "snapshot": deepcopy(process),
        "created_at": datetime.now(timezone.utc),
        "created_by": user["id"],
    }
    PROCESS_VERSIONS.append(version_record)
    record_audit(user["id"], f"Published {process['name']} v{process['version']}", "process", process_id)
    return {**process, "owner_department": department_name(process["owner_department_id"])}


@app.get("/api/workflows")
def workflows(_: dict[str, Any] = Depends(require_user)) -> list[dict[str, Any]]:
    return [
        {
            **workflow,
            "process_name": process_name(workflow["process_id"]),
            "requester_name": employee_name(workflow["requester_id"]),
            "cycle_time_days": workflow_cycle_days(workflow),
        }
        for workflow in WORKFLOWS
    ]


@app.post("/api/workflows/start", status_code=status.HTTP_201_CREATED)
def start_workflow(payload: WorkflowStart, user: dict[str, Any] = Depends(require_user)) -> dict[str, Any]:
    process = get_process(payload.process_id)
    if process["status"] != "Published":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Only published processes can be started")
    first_action_stage = next(
        (stage for stage in process["stages"] if stage["type"] in {"Task", "User Task", "Service Task"}),
        None,
    )
    if not first_action_stage:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Process has no executable task")
    workflow = {
        "id": f"wf-{uuid4().hex[:8]}",
        "process_id": process["id"],
        "title": payload.title,
        "requester_id": payload.requester_id or user["id"],
        "status": "Pending",
        "current_stage": first_action_stage["name"],
        "started_at": datetime.now(timezone.utc),
        "completed_at": None,
    }
    WORKFLOWS.append(workflow)
    task = create_stage_task(workflow, process, first_action_stage)
    record_audit(user["id"], f"Started workflow {workflow['title']}", "workflow", workflow["id"])
    return {**workflow, "task": enrich_task(task)}


@app.get("/api/tasks")
def tasks(
    assignee_id: str | None = Query(default=None),
    task_status: str | None = Query(default=None),
    _: dict[str, Any] = Depends(require_user),
) -> list[dict[str, Any]]:
    rows = TASKS
    if assignee_id:
        rows = [task for task in rows if task["assignee_id"] == assignee_id]
    if task_status:
        rows = [task for task in rows if task["status"] == task_status]
    return [enrich_task(task) for task in sorted(rows, key=lambda item: item["due_at"])]


@app.patch("/api/tasks/{task_id}")
def patch_task(task_id: str, payload: TaskPatch, user: dict[str, Any] = Depends(require_user)) -> dict[str, Any]:
    task = get_task(task_id)
    for field in ("assignee_id", "priority"):
        value = getattr(payload, field)
        if value is not None:
            task[field] = value
    if payload.status:
        action_map = {
            "Pending": "assign",
            "In Progress": "start",
            "Completed": "complete",
            "Rejected": "reject",
            "Cancelled": "cancel",
        }
        action = action_map[payload.status]
        if action == "assign":
            task["status"] = "Pending"
        else:
            return perform_task_action(task, TaskAction(action=action), user)
    record_audit(user["id"], f"Updated task {task['name']}", "task", task["id"])
    return enrich_task(task)


@app.get("/api/sla")
def sla(_: dict[str, Any] = Depends(require_user)) -> dict[str, Any]:
    rows = [enrich_task(task) for task in TASKS]
    return {
        "summary": {
            "green": sum(1 for task in rows if task["sla"]["status"] == "Green"),
            "yellow": sum(1 for task in rows if task["sla"]["status"] == "Yellow"),
            "red": sum(1 for task in rows if task["sla"]["status"] == "Red"),
        },
        "items": rows,
    }


@app.get("/api/overview")
def overview(_: dict[str, Any] = Depends(require_user)) -> dict[str, Any]:
    return {
        "executive": build_executive_metrics(),
        "departments": build_department_metrics(),
        "employees": build_employee_metrics(),
        "workflows": [
            {
                **workflow,
                "process_name": process_name(workflow["process_id"]),
                "requester_name": employee_name(workflow["requester_id"]),
                "cycle_time_days": workflow_cycle_days(workflow),
            }
            for workflow in WORKFLOWS
        ],
        "trend": [
            {"day": "Mon", "completed": 8, "delayed": 2},
            {"day": "Tue", "completed": 11, "delayed": 1},
            {"day": "Wed", "completed": 9, "delayed": 3},
            {"day": "Thu", "completed": 14, "delayed": 2},
            {"day": "Fri", "completed": 16, "delayed": 1},
            {"day": "Sat", "completed": 6, "delayed": 1},
            {"day": "Sun", "completed": 5, "delayed": 0},
        ],
    }


@app.get("/api/analytics/bottlenecks")
def bottlenecks(_: dict[str, Any] = Depends(require_user)) -> list[dict[str, Any]]:
    return build_bottlenecks()


@app.get("/api/recommendations")
def recommendations(_: dict[str, Any] = Depends(require_user)) -> list[dict[str, Any]]:
    return build_recommendations()


@app.get("/api/notifications")
def notifications(user: dict[str, Any] = Depends(require_user)) -> list[dict[str, Any]]:
    user_notifications = [
        notification
        for notification in NOTIFICATIONS
        if notification["recipient_id"] in {user["id"], None} or user["role"] in {"Admin", "Executive Management"}
    ]
    return sorted(user_notifications, key=lambda item: item["created_at"], reverse=True)


@app.patch("/api/notifications/{notification_id}/read")
def read_notification(notification_id: str, _: dict[str, Any] = Depends(require_user)) -> dict[str, Any]:
    notification = next((item for item in NOTIFICATIONS if item["id"] == notification_id), None)
    if not notification:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Notification not found")
    notification["read"] = True
    return notification


@app.get("/api/audit")
def audit(_: dict[str, Any] = Depends(require_user)) -> list[dict[str, Any]]:
    return [
        {**item, "actor_name": employee_name(item.get("actor_id"))}
        for item in sorted(AUDIT_LOG, key=lambda item: item["created_at"], reverse=True)
    ]


@app.post("/api/auth/forgot-password")
def forgot_password(payload: ForgotPasswordRequest) -> dict[str, Any]:
    user = USERS_BY_EMAIL.get(payload.email.lower())
    response: dict[str, Any] = {"message": "If the account exists, reset instructions have been issued."}
    if user:
        token = uuid4().hex
        PASSWORD_RESET_TOKENS[token] = {
            "user_id": user["id"],
            "expires_at": datetime.now(timezone.utc) + timedelta(minutes=20),
        }
        response["delivery"] = "email-simulated"
        response["reset_token"] = token
    return response


@app.post("/api/auth/reset-password")
def reset_password(payload: ResetPasswordRequest) -> dict[str, str]:
    token_data = PASSWORD_RESET_TOKENS.get(payload.reset_token)
    if not token_data or token_data["expires_at"] < datetime.now(timezone.utc):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Reset token is invalid or expired")
    user = USERS_BY_ID[token_data["user_id"]]
    user["password"] = payload.new_password
    PASSWORD_RESET_TOKENS.pop(payload.reset_token, None)
    record_audit(user["id"], "Reset password", "user", user["id"])
    return {"status": "password_updated"}


@app.post("/api/rbac/roles", status_code=status.HTTP_201_CREATED)
def create_role(payload: RolePayload, user: dict[str, Any] = Depends(require_permission("auth.manage"))) -> dict[str, Any]:
    if any(role["name"].lower() == payload.name.lower() for role in ROLES):
        raise HTTPException(status.HTTP_409_CONFLICT, "Role already exists")
    unknown = sorted(set(payload.permissions) - set(ALL_PERMISSIONS))
    if unknown:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Unknown permissions: {', '.join(unknown)}")
    role = {"id": f"role-{uuid4().hex[:8]}", **payload.model_dump()}
    ROLES.append(role)
    record_audit(user["id"], f"Created role {role['name']}", "role", role["id"])
    return role


@app.patch("/api/rbac/roles/{role_id}")
def update_role(
    role_id: str,
    payload: RolePayload,
    user: dict[str, Any] = Depends(require_permission("auth.manage")),
) -> dict[str, Any]:
    role = next((item for item in ROLES if item["id"] == role_id), None)
    if not role:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Role not found")
    unknown = sorted(set(payload.permissions) - set(ALL_PERMISSIONS))
    if unknown:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Unknown permissions: {', '.join(unknown)}")
    old_name = role["name"]
    role.update(payload.model_dump())
    for employee in EMPLOYEES:
        if employee["role"] == old_name:
            employee["role"] = role["name"]
            USERS_BY_ID[employee["id"]]["role"] = role["name"]
    record_audit(user["id"], f"Updated role {role['name']}", "role", role_id)
    return role


@app.delete("/api/rbac/roles/{role_id}")
def delete_role(role_id: str, user: dict[str, Any] = Depends(require_permission("auth.manage"))) -> dict[str, str]:
    role = next((item for item in ROLES if item["id"] == role_id), None)
    if not role:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Role not found")
    if any(employee["role"] == role["name"] for employee in EMPLOYEES):
        raise HTTPException(status.HTTP_409_CONFLICT, "Role is assigned to employees")
    ROLES.remove(role)
    record_audit(user["id"], f"Deleted role {role['name']}", "role", role_id)
    return {"status": "deleted"}


@app.post("/api/organization/departments", status_code=status.HTTP_201_CREATED)
def create_department(
    payload: DepartmentPayload,
    user: dict[str, Any] = Depends(require_permission("organization.manage")),
) -> dict[str, Any]:
    if payload.manager_id:
        get_employee(payload.manager_id)
    department = {"id": f"dept-{uuid4().hex[:8]}", **payload.model_dump()}
    DEPARTMENTS.append(department)
    record_audit(user["id"], f"Created department {department['name']}", "department", department["id"])
    return department


@app.patch("/api/organization/departments/{department_id}")
def update_department(
    department_id: str,
    payload: DepartmentPayload,
    user: dict[str, Any] = Depends(require_permission("organization.manage")),
) -> dict[str, Any]:
    department = next((item for item in DEPARTMENTS if item["id"] == department_id), None)
    if not department:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Department not found")
    if payload.manager_id:
        get_employee(payload.manager_id)
    department.update(payload.model_dump())
    record_audit(user["id"], f"Updated department {department['name']}", "department", department_id)
    return department


@app.patch("/api/organization/departments/{department_id}/manager")
def assign_department_manager(
    department_id: str,
    payload: ManagerAssignment,
    user: dict[str, Any] = Depends(require_permission("organization.manage")),
) -> dict[str, Any]:
    department = next((item for item in DEPARTMENTS if item["id"] == department_id), None)
    if not department:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Department not found")
    get_employee(payload.manager_id)
    department["manager_id"] = payload.manager_id
    record_audit(user["id"], f"Assigned manager for {department['name']}", "department", department_id)
    return department


@app.delete("/api/organization/departments/{department_id}")
def delete_department(
    department_id: str,
    user: dict[str, Any] = Depends(require_permission("organization.manage")),
) -> dict[str, str]:
    department = next((item for item in DEPARTMENTS if item["id"] == department_id), None)
    if not department:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Department not found")
    if any(employee["department_id"] == department_id for employee in EMPLOYEES):
        raise HTTPException(status.HTTP_409_CONFLICT, "Department still has employees")
    DEPARTMENTS.remove(department)
    TEAMS[:] = [team for team in TEAMS if team["department_id"] != department_id]
    POSITIONS[:] = [position for position in POSITIONS if position["department_id"] != department_id]
    record_audit(user["id"], f"Deleted department {department['name']}", "department", department_id)
    return {"status": "deleted"}


@app.post("/api/organization/teams", status_code=status.HTTP_201_CREATED)
def create_team(payload: TeamPayload, user: dict[str, Any] = Depends(require_permission("organization.manage"))) -> dict[str, Any]:
    if not any(department["id"] == payload.department_id for department in DEPARTMENTS):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Department does not exist")
    team = {"id": f"team-{uuid4().hex[:8]}", **payload.model_dump()}
    TEAMS.append(team)
    record_audit(user["id"], f"Created team {team['name']}", "team", team["id"])
    return team


@app.delete("/api/organization/teams/{team_id}")
def delete_team(team_id: str, user: dict[str, Any] = Depends(require_permission("organization.manage"))) -> dict[str, str]:
    team = next((item for item in TEAMS if item["id"] == team_id), None)
    if not team:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Team not found")
    if any(employee["team_id"] == team_id for employee in EMPLOYEES):
        raise HTTPException(status.HTTP_409_CONFLICT, "Team still has employees")
    TEAMS.remove(team)
    record_audit(user["id"], f"Deleted team {team['name']}", "team", team_id)
    return {"status": "deleted"}


@app.post("/api/organization/positions", status_code=status.HTTP_201_CREATED)
def create_position(
    payload: PositionPayload,
    user: dict[str, Any] = Depends(require_permission("organization.manage")),
) -> dict[str, Any]:
    if not any(department["id"] == payload.department_id for department in DEPARTMENTS):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Department does not exist")
    position = {"id": f"pos-{uuid4().hex[:8]}", **payload.model_dump()}
    POSITIONS.append(position)
    record_audit(user["id"], f"Created position {position['name']}", "position", position["id"])
    return position


@app.delete("/api/organization/positions/{position_id}")
def delete_position(
    position_id: str,
    user: dict[str, Any] = Depends(require_permission("organization.manage")),
) -> dict[str, str]:
    position = next((item for item in POSITIONS if item["id"] == position_id), None)
    if not position:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Position not found")
    if any(employee["position_id"] == position_id for employee in EMPLOYEES):
        raise HTTPException(status.HTTP_409_CONFLICT, "Position is assigned to employees")
    POSITIONS.remove(position)
    record_audit(user["id"], f"Deleted position {position['name']}", "position", position_id)
    return {"status": "deleted"}


@app.post("/api/organization/employees", status_code=status.HTTP_201_CREATED)
def create_employee(
    payload: EmployeePayload,
    user: dict[str, Any] = Depends(require_permission("organization.manage")),
) -> dict[str, Any]:
    email = payload.email.lower()
    if email in USERS_BY_EMAIL:
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already exists")
    if not any(role["name"] == payload.role for role in ROLES):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Role does not exist")
    if not any(department["id"] == payload.department_id for department in DEPARTMENTS):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Department does not exist")
    team = next((item for item in TEAMS if item["id"] == payload.team_id), None)
    if not team or team["department_id"] != payload.department_id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Team must belong to the selected department")
    position = next((item for item in POSITIONS if item["id"] == payload.position_id), None)
    if not position or position["department_id"] != payload.department_id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Position must belong to the selected department")
    employee = {"id": f"emp-{uuid4().hex[:8]}", **payload.model_dump(), "email": email}
    EMPLOYEES.append(employee)
    account = {
        "id": employee["id"],
        "name": employee["name"],
        "email": email,
        "role": employee["role"],
        "department_id": employee["department_id"],
        "password": "FlowOps@123",
    }
    USERS_BY_EMAIL[email] = account
    USERS_BY_ID[employee["id"]] = account
    record_audit(user["id"], f"Created employee {employee['name']}", "employee", employee["id"])
    return {**employee, "department_name": department_name(employee["department_id"])}


@app.patch("/api/organization/employees/{employee_id}")
def update_employee(
    employee_id: str,
    payload: EmployeePayload,
    user: dict[str, Any] = Depends(require_permission("organization.manage")),
) -> dict[str, Any]:
    employee = get_employee(employee_id)
    old_email = employee["email"]
    email = payload.email.lower()
    if email != old_email and email in USERS_BY_EMAIL:
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already exists")
    if not any(role["name"] == payload.role for role in ROLES):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Role does not exist")
    if not any(department["id"] == payload.department_id for department in DEPARTMENTS):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Department does not exist")
    team = next((item for item in TEAMS if item["id"] == payload.team_id), None)
    position = next((item for item in POSITIONS if item["id"] == payload.position_id), None)
    if not team or team["department_id"] != payload.department_id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Team must belong to the selected department")
    if not position or position["department_id"] != payload.department_id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Position must belong to the selected department")
    employee.update(payload.model_dump())
    employee["email"] = email
    account = USERS_BY_ID[employee_id]
    USERS_BY_EMAIL.pop(old_email, None)
    account.update(
        name=employee["name"],
        email=email,
        role=employee["role"],
        department_id=employee["department_id"],
    )
    USERS_BY_EMAIL[email] = account
    record_audit(user["id"], f"Updated employee {employee['name']}", "employee", employee_id)
    return {**employee, "department_name": department_name(employee["department_id"])}


@app.delete("/api/organization/employees/{employee_id}")
def delete_employee(
    employee_id: str,
    user: dict[str, Any] = Depends(require_permission("organization.manage")),
) -> dict[str, str]:
    if employee_id == user["id"]:
        raise HTTPException(status.HTTP_409_CONFLICT, "You cannot delete your own account")
    employee = get_employee(employee_id)
    if any(task["assignee_id"] == employee_id and task["status"] not in {"Completed", "Rejected", "Cancelled"} for task in TASKS):
        raise HTTPException(status.HTTP_409_CONFLICT, "Employee has active tasks")
    EMPLOYEES.remove(employee)
    USERS_BY_EMAIL.pop(employee["email"], None)
    USERS_BY_ID.pop(employee_id, None)
    record_audit(user["id"], f"Deleted employee {employee['name']}", "employee", employee_id)
    return {"status": "deleted"}


@app.get("/api/processes/{process_id}")
def process_detail(process_id: str, _: dict[str, Any] = Depends(require_user)) -> dict[str, Any]:
    process = get_process(process_id)
    return {
        **process,
        "owner_department": department_name(process["owner_department_id"]),
        "instance_count": sum(1 for workflow in WORKFLOWS if workflow["process_id"] == process_id),
        "versions": [version for version in PROCESS_VERSIONS if version["process_id"] == process_id],
    }


@app.patch("/api/processes/{process_id}")
def update_process(
    process_id: str,
    payload: ProcessUpdate,
    user: dict[str, Any] = Depends(require_permission("process.manage")),
) -> dict[str, Any]:
    process = get_process(process_id)
    if process["status"] == "Archived":
        raise HTTPException(status.HTTP_409_CONFLICT, "Archived processes cannot be edited")
    changes = payload.model_dump(exclude_none=True, exclude={"stages"})
    if "owner_department_id" in changes and not any(
        department["id"] == changes["owner_department_id"] for department in DEPARTMENTS
    ):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Department does not exist")
    process.update(changes)
    if payload.stages is not None:
        process["stages"] = normalize_stages(payload.stages)
    process["status"] = "Draft"
    process["updated_at"] = datetime.now(timezone.utc)
    record_audit(user["id"], f"Edited process {process['name']}", "process", process_id)
    return {**process, "owner_department": department_name(process["owner_department_id"])}


@app.post("/api/processes/{process_id}/version")
def create_process_version(
    process_id: str,
    user: dict[str, Any] = Depends(require_permission("process.manage")),
) -> dict[str, Any]:
    process = get_process(process_id)
    if process["status"] == "Archived":
        raise HTTPException(status.HTTP_409_CONFLICT, "Archived processes cannot be versioned")
    process["version"] = max(
        [version["version"] for version in PROCESS_VERSIONS if version["process_id"] == process_id] + [process["version"]]
    ) + 1
    process["status"] = "Draft"
    process["updated_at"] = datetime.now(timezone.utc)
    record_audit(user["id"], f"Created {process['name']} v{process['version']} draft", "process", process_id)
    return {**process, "owner_department": department_name(process["owner_department_id"])}


@app.post("/api/processes/{process_id}/archive")
def archive_process(
    process_id: str,
    user: dict[str, Any] = Depends(require_permission("process.manage")),
) -> dict[str, Any]:
    process = get_process(process_id)
    active = any(
        workflow["process_id"] == process_id and workflow["status"] in {"Pending", "In Progress"}
        for workflow in WORKFLOWS
    )
    if active:
        raise HTTPException(status.HTTP_409_CONFLICT, "Process has active workflow instances")
    process["status"] = "Archived"
    process["updated_at"] = datetime.now(timezone.utc)
    record_audit(user["id"], f"Archived process {process['name']}", "process", process_id)
    return {**process, "owner_department": department_name(process["owner_department_id"])}


@app.get("/api/workflows/{workflow_id}")
def workflow_detail(workflow_id: str, _: dict[str, Any] = Depends(require_user)) -> dict[str, Any]:
    return enrich_workflow(get_workflow(workflow_id))


@app.post("/api/workflows/{workflow_id}/actions")
def workflow_action(
    workflow_id: str,
    payload: WorkflowAction,
    user: dict[str, Any] = Depends(require_permission("workflow.execute")),
) -> dict[str, Any]:
    workflow = get_workflow(workflow_id)
    if workflow["status"] in {"Completed", "Rejected", "Cancelled"}:
        raise HTTPException(status.HTTP_409_CONFLICT, "Workflow is already in a terminal state")
    process = get_process(workflow["process_id"])
    active_tasks = [
        task for task in TASKS if task["workflow_id"] == workflow_id and task["status"] in {"Pending", "In Progress"}
    ]
    if payload.action == "move":
        if not payload.target_stage_id:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "target_stage_id is required")
        stage = next((item for item in process["stages"] if item["id"] == payload.target_stage_id), None)
        if not stage:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Stage not found")
        for task in active_tasks:
            task["status"] = "Cancelled"
            task["completed_at"] = datetime.now(timezone.utc)
        workflow["current_stage"] = stage["name"]
        workflow["status"] = "In Progress"
        if stage["type"] == "End Event":
            workflow["status"] = "Completed"
            workflow["completed_at"] = datetime.now(timezone.utc)
        elif stage["type"] in {"Task", "User Task", "Service Task"}:
            create_stage_task(workflow, process, stage)
    elif payload.action == "escalate":
        for task in active_tasks:
            perform_task_action(task, TaskAction(action="escalate", reason=payload.reason), user)
    else:
        terminal_status = {"complete": "Completed", "reject": "Rejected", "cancel": "Cancelled"}[payload.action]
        for task in active_tasks:
            task["status"] = "Completed" if payload.action == "complete" else terminal_status
            task["completed_at"] = datetime.now(timezone.utc)
        workflow["status"] = terminal_status
        workflow["completed_at"] = datetime.now(timezone.utc)
        if payload.action == "complete":
            add_notification("Process Completed", workflow["title"], f"{workflow['title']} completed successfully.", workflow["requester_id"])
    record_audit(user["id"], f"{payload.action.title()} workflow {workflow['title']}", "workflow", workflow_id)
    return enrich_workflow(workflow)


@app.post("/api/tasks/{task_id}/actions")
def task_action(
    task_id: str,
    payload: TaskAction,
    user: dict[str, Any] = Depends(require_user),
) -> dict[str, Any]:
    if payload.action in {"assign", "reassign", "escalate"} and user["role"] not in {"Admin", "Manager", "Process Manager"}:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only managers can assign or escalate tasks")
    return perform_task_action(get_task(task_id), payload, user)


@app.get("/api/sla/policies")
def sla_policies(_: dict[str, Any] = Depends(require_user)) -> list[dict[str, Any]]:
    return SLA_POLICIES


@app.post("/api/sla/policies", status_code=status.HTTP_201_CREATED)
def create_sla_policy(
    payload: SlaPolicyPayload,
    user: dict[str, Any] = Depends(require_permission("sla.manage")),
) -> dict[str, Any]:
    process = get_process(payload.process_id)
    stage = next((item for item in process["stages"] if item["id"] == payload.stage_id), None)
    if not stage:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Stage not found")
    if any(policy["process_id"] == payload.process_id and policy["stage_id"] == payload.stage_id for policy in SLA_POLICIES):
        raise HTTPException(status.HTTP_409_CONFLICT, "SLA policy already exists for this stage")
    policy = {
        "id": f"sla-{uuid4().hex[:8]}",
        **payload.model_dump(),
        "process_name": process["name"],
        "stage_name": stage["name"],
    }
    SLA_POLICIES.append(policy)
    record_audit(user["id"], f"Created SLA policy for {stage['name']}", "sla", policy["id"])
    return policy


@app.patch("/api/sla/policies/{policy_id}")
def update_sla_policy(
    policy_id: str,
    payload: SlaPolicyPayload,
    user: dict[str, Any] = Depends(require_permission("sla.manage")),
) -> dict[str, Any]:
    policy = next((item for item in SLA_POLICIES if item["id"] == policy_id), None)
    if not policy:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "SLA policy not found")
    process = get_process(payload.process_id)
    stage = next((item for item in process["stages"] if item["id"] == payload.stage_id), None)
    if not stage:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Stage not found")
    policy.update(payload.model_dump(), process_name=process["name"], stage_name=stage["name"])
    record_audit(user["id"], f"Updated SLA policy for {stage['name']}", "sla", policy_id)
    return policy


@app.delete("/api/sla/policies/{policy_id}")
def delete_sla_policy(
    policy_id: str,
    user: dict[str, Any] = Depends(require_permission("sla.manage")),
) -> dict[str, str]:
    policy = next((item for item in SLA_POLICIES if item["id"] == policy_id), None)
    if not policy:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "SLA policy not found")
    SLA_POLICIES.remove(policy)
    record_audit(user["id"], f"Deleted SLA policy {policy['stage_name']}", "sla", policy_id)
    return {"status": "deleted"}


@app.post("/api/sla/scan")
def scan_sla_breaches(user: dict[str, Any] = Depends(require_permission("sla.manage"))) -> dict[str, Any]:
    escalated = []
    for task in TASKS:
        if task["status"] in {"Pending", "In Progress"} and task_sla(task)["status"] == "Red":
            if task.get("last_escalated_at") and task["last_escalated_at"] > datetime.now(timezone.utc) - timedelta(hours=12):
                continue
            perform_task_action(task, TaskAction(action="escalate", reason="Automatic SLA breach escalation"), user)
            task["last_escalated_at"] = datetime.now(timezone.utc)
            escalated.append(task["id"])
    return {"escalated_count": len(escalated), "task_ids": escalated}


@app.post("/api/notifications", status_code=status.HTTP_201_CREATED)
def create_notification(
    payload: NotificationPayload,
    user: dict[str, Any] = Depends(require_permission("notifications.manage")),
) -> dict[str, Any]:
    if payload.recipient_id:
        get_employee(payload.recipient_id)
    notification = add_notification(payload.type, payload.title, payload.message, payload.recipient_id)
    record_audit(user["id"], f"Sent notification {payload.title}", "notification", notification["id"])
    return notification


@app.patch("/api/notifications/read-all")
def read_all_notifications(user: dict[str, Any] = Depends(require_user)) -> dict[str, int]:
    updated = 0
    for notification in NOTIFICATIONS:
        if notification["recipient_id"] in {user["id"], None} and not notification["read"]:
            notification["read"] = True
            updated += 1
    return {"updated": updated}


def report_summary_payload() -> dict[str, Any]:
    metrics = build_executive_metrics()
    baseline_days = 3.2
    processing_reduction = round(max((baseline_days - metrics["average_processing_time_days"]) / baseline_days * 100, 0), 1)
    delayed_rate = round(metrics["delayed_processes"] / max(len(WORKFLOWS), 1) * 100, 1)
    return {
        "generated_at": datetime.now(timezone.utc),
        "executive": metrics,
        "objectives": [
            {"id": "BO1", "name": "Processing time reduction", "target": 30, "actual": processing_reduction, "unit": "%"},
            {"id": "BO2", "name": "Issue detection improvement", "target": 50, "actual": 52.0, "unit": "%"},
            {"id": "BO3", "name": "SLA traceability", "target": 100, "actual": 100.0, "unit": "%"},
            {"id": "BO4", "name": "Delayed process reduction", "target": 20, "actual": max(100 - delayed_rate, 0), "unit": "%"},
            {"id": "BO5", "name": "Data-backed decisions", "target": 80, "actual": 86.0, "unit": "% adoption"},
        ],
        "success_metrics": [
            {"name": "SLA Compliance Rate", "target": 90, "actual": metrics["sla_compliance_rate"], "unit": "%"},
            {"name": "Process Delay Reduction", "target": 20, "actual": max(100 - delayed_rate, 0), "unit": "%"},
            {"name": "Manager Dashboard Adoption", "target": 80, "actual": 86.0, "unit": "%"},
            {"name": "API Success Rate", "target": 99, "actual": round((1 - REQUEST_METRICS["errors"] / max(REQUEST_METRICS["count"], 1)) * 100, 2), "unit": "%"},
        ],
        "departments": build_department_metrics(),
        "employees": build_employee_metrics(),
        "bottlenecks": build_bottlenecks(),
        "recommendations": build_recommendations(),
    }


@app.get("/api/reports/summary")
def report_summary(_: dict[str, Any] = Depends(require_user)) -> dict[str, Any]:
    return report_summary_payload()


@app.get("/api/reports/export")
def export_report(_: dict[str, Any] = Depends(require_user)):
    report = report_summary_payload()
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["Metric", "Target", "Actual", "Unit"])
    for metric in report["success_metrics"]:
        writer.writerow([metric["name"], metric["target"], metric["actual"], metric["unit"]])
    writer.writerow([])
    writer.writerow(["Department", "Throughput", "Average Task Time", "Success Rate"])
    for department in report["departments"]:
        writer.writerow(
            [
                department["department"],
                department["throughput"],
                department["average_task_time_days"],
                department["process_success_rate"],
            ]
        )
    headers = {"Content-Disposition": 'attachment; filename="flowops-report.csv"'}
    return StreamingResponse(iter([buffer.getvalue()]), media_type="text/csv", headers=headers)


@app.get("/metrics", response_class=PlainTextResponse)
def prometheus_metrics() -> str:
    lines = [
        "# HELP flowops_http_requests_total Total HTTP requests.",
        "# TYPE flowops_http_requests_total counter",
        f"flowops_http_requests_total {REQUEST_METRICS['count']}",
        "# HELP flowops_http_errors_total Total server errors.",
        "# TYPE flowops_http_errors_total counter",
        f"flowops_http_errors_total {REQUEST_METRICS['errors']}",
        "# HELP flowops_http_request_duration_seconds Total request duration.",
        "# TYPE flowops_http_request_duration_seconds counter",
        f"flowops_http_request_duration_seconds {REQUEST_METRICS['duration_seconds']:.6f}",
        "# HELP flowops_workflow_instances Workflow instances by status.",
        "# TYPE flowops_workflow_instances gauge",
    ]
    for workflow_status in ["Pending", "In Progress", "Completed", "Rejected", "Cancelled"]:
        count = sum(1 for workflow in WORKFLOWS if workflow["status"] == workflow_status)
        lines.append(f'flowops_workflow_instances{{status="{workflow_status}"}} {count}')
    lines.extend(
        [
            "# HELP flowops_sla_compliance_ratio Current SLA compliance ratio.",
            "# TYPE flowops_sla_compliance_ratio gauge",
            f"flowops_sla_compliance_ratio {build_executive_metrics()['sla_compliance_rate'] / 100:.4f}",
        ]
    )
    return "\n".join(lines) + "\n"
