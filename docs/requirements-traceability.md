# FlowOps Requirements Traceability

| Requirement | Implementation |
| --- | --- |
| Authentication, JWT, refresh, logout, forgot password | `/api/auth/*`, Login screen |
| Role and permission management | `/api/rbac/*`, Administration view |
| Department, team, position, employee, manager assignment | `/api/organization/*`, Organization view |
| BPMN process create, edit, publish, version, archive | `/api/processes/*`, Process Designer |
| Workflow start, move, reject, complete, cancel, escalate | `/api/workflows/*`, workflow state machine |
| Task view, claim, assign, reassign, complete, reject, escalate | `/api/tasks/*`, Task Management |
| SLA define, track, warning, breach escalation | `/api/sla/*`, SLA view |
| Executive, department, employee KPI | `/api/overview`, Dashboard and Reports |
| Bottleneck metrics and root cause | `/api/analytics/bottlenecks`, Analytics view |
| Rules-based recommendations | `/api/recommendations`, Analytics view |
| In-app notifications | `/api/notifications/*`, notification panel |
| Reports and CSV export | `/api/reports/*`, Reports view |
| Audit all process activities | `/api/audit`, Administration audit log |
| Monitoring | `/metrics`, Prometheus and Grafana services |
| Containerization | Backend/frontend Dockerfiles and `docker-compose.yml` |
| CI/CD | `.github/workflows/ci.yml` |

The local reference implementation keeps seeded operational data in memory. The Compose stack provisions PostgreSQL, MongoDB, Redis, and Kafka as the target production infrastructure boundary.
