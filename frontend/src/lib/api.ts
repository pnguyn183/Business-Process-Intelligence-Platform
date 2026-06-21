import type {
  AppNotification,
  AuditEvent,
  Bottleneck,
  FlowProcess,
  Organization,
  Overview,
  RbacData,
  Recommendation,
  ReportSummary,
  Session,
  SlaPolicy,
  SlaResponse,
  TaskItem,
  WorkflowItem
} from "../types";

const API_URL = import.meta.env.VITE_API_URL ?? "";

async function request<T>(path: string, options: RequestInit = {}, token?: string): Promise<T> {
  const headers = new Headers(options.headers);
  headers.set("Content-Type", "application/json");
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const response = await fetch(`${API_URL}${path}`, {
    ...options,
    headers
  });

  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `Request failed with ${response.status}`);
  }

  return response.json() as Promise<T>;
}

async function requestBlob(path: string, token: string): Promise<Blob> {
  const response = await fetch(`${API_URL}${path}`, {
    headers: { Authorization: `Bearer ${token}` }
  });
  if (!response.ok) throw new Error(await response.text());
  return response.blob();
}

export const api = {
  apiUrl: API_URL,
  login(email: string, password: string) {
    return request<Session>("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password })
    });
  },
  forgotPassword(email: string) {
    return request<{ message: string; reset_token?: string }>("/api/auth/forgot-password", {
      method: "POST",
      body: JSON.stringify({ email })
    });
  },
  resetPassword(reset_token: string, new_password: string) {
    return request<{ status: string }>("/api/auth/reset-password", {
      method: "POST",
      body: JSON.stringify({ reset_token, new_password })
    });
  },
  overview(token: string) {
    return request<Overview>("/api/overview", {}, token);
  },
  processes(token: string) {
    return request<FlowProcess[]>("/api/processes", {}, token);
  },
  tasks(token: string) {
    return request<TaskItem[]>("/api/tasks", {}, token);
  },
  workflows(token: string) {
    return request<WorkflowItem[]>("/api/workflows", {}, token);
  },
  sla(token: string) {
    return request<SlaResponse>("/api/sla", {}, token);
  },
  bottlenecks(token: string) {
    return request<Bottleneck[]>("/api/analytics/bottlenecks", {}, token);
  },
  recommendations(token: string) {
    return request<Recommendation[]>("/api/recommendations", {}, token);
  },
  organization(token: string) {
    return request<Organization>("/api/organization", {}, token);
  },
  notifications(token: string) {
    return request<AppNotification[]>("/api/notifications", {}, token);
  },
  rbac(token: string) {
    return request<RbacData>("/api/rbac", {}, token);
  },
  audit(token: string) {
    return request<AuditEvent[]>("/api/audit", {}, token);
  },
  reports(token: string) {
    return request<ReportSummary>("/api/reports/summary", {}, token);
  },
  downloadReport(token: string) {
    return requestBlob("/api/reports/export", token);
  },
  slaPolicies(token: string) {
    return request<SlaPolicy[]>("/api/sla/policies", {}, token);
  },
  createProcess(
    token: string,
    payload: { name: string; description: string; owner_department_id: string; stages: string[] }
  ) {
    return request<FlowProcess>(
      "/api/processes",
      {
        method: "POST",
        body: JSON.stringify(payload)
      },
      token
    );
  },
  publishProcess(token: string, processId: string) {
    return request<FlowProcess>(
      `/api/processes/${processId}/publish`,
      {
        method: "POST"
      },
      token
    );
  },
  updateProcess(
    token: string,
    processId: string,
    payload: { name?: string; description?: string; owner_department_id?: string; stages?: Array<string | { name: string; type: string; sla_days: number }> }
  ) {
    return request<FlowProcess>(`/api/processes/${processId}`, { method: "PATCH", body: JSON.stringify(payload) }, token);
  },
  versionProcess(token: string, processId: string) {
    return request<FlowProcess>(`/api/processes/${processId}/version`, { method: "POST" }, token);
  },
  archiveProcess(token: string, processId: string) {
    return request<FlowProcess>(`/api/processes/${processId}/archive`, { method: "POST" }, token);
  },
  startWorkflow(token: string, payload: { process_id: string; title: string }) {
    return request<WorkflowItem & { task: TaskItem }>(
      "/api/workflows/start",
      {
        method: "POST",
        body: JSON.stringify(payload)
      },
      token
    );
  },
  updateTask(
    token: string,
    taskId: string,
    payload: Partial<Pick<TaskItem, "status" | "assignee_id" | "priority">>
  ) {
    return request<TaskItem>(
      `/api/tasks/${taskId}`,
      {
        method: "PATCH",
        body: JSON.stringify(payload)
      },
      token
    );
  },
  taskAction(
    token: string,
    taskId: string,
    payload: { action: "claim" | "assign" | "reassign" | "start" | "complete" | "reject" | "cancel" | "escalate"; assignee_id?: string; reason?: string }
  ) {
    return request<TaskItem>(`/api/tasks/${taskId}/actions`, { method: "POST", body: JSON.stringify(payload) }, token);
  },
  createDepartment(token: string, payload: { name: string; manager_id?: string | null }) {
    return request("/api/organization/departments", { method: "POST", body: JSON.stringify(payload) }, token);
  },
  assignDepartmentManager(token: string, departmentId: string, manager_id: string) {
    return request(`/api/organization/departments/${departmentId}/manager`, { method: "PATCH", body: JSON.stringify({ manager_id }) }, token);
  },
  createTeam(token: string, payload: { name: string; department_id: string }) {
    return request("/api/organization/teams", { method: "POST", body: JSON.stringify(payload) }, token);
  },
  createPosition(token: string, payload: { name: string; department_id: string }) {
    return request("/api/organization/positions", { method: "POST", body: JSON.stringify(payload) }, token);
  },
  createEmployee(token: string, payload: { name: string; email: string; role: string; department_id: string; team_id: string; position_id: string }) {
    return request("/api/organization/employees", { method: "POST", body: JSON.stringify(payload) }, token);
  },
  createRole(token: string, payload: { name: string; permissions: string[] }) {
    return request("/api/rbac/roles", { method: "POST", body: JSON.stringify(payload) }, token);
  },
  updateRole(token: string, roleId: string, payload: { name: string; permissions: string[] }) {
    return request(`/api/rbac/roles/${roleId}`, { method: "PATCH", body: JSON.stringify(payload) }, token);
  },
  createSlaPolicy(token: string, payload: Omit<SlaPolicy, "id" | "process_name" | "stage_name">) {
    return request<SlaPolicy>("/api/sla/policies", { method: "POST", body: JSON.stringify(payload) }, token);
  },
  updateSlaPolicy(token: string, policyId: string, payload: Omit<SlaPolicy, "id" | "process_name" | "stage_name">) {
    return request<SlaPolicy>(`/api/sla/policies/${policyId}`, { method: "PATCH", body: JSON.stringify(payload) }, token);
  },
  scanSla(token: string) {
    return request<{ escalated_count: number; task_ids: string[] }>("/api/sla/scan", { method: "POST" }, token);
  },
  markNotificationRead(token: string, notificationId: string) {
    return request<AppNotification>(
      `/api/notifications/${notificationId}/read`,
      {
        method: "PATCH"
      },
      token
    );
  },
  markAllNotificationsRead(token: string) {
    return request<{ updated: number }>("/api/notifications/read-all", { method: "PATCH" }, token);
  }
};
