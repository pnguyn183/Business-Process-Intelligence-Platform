import {
  Activity,
  AlertTriangle,
  Archive,
  ArrowUpCircle,
  Bell,
  Building2,
  CheckCircle2,
  Circle,
  Diamond,
  Download,
  FileBarChart,
  Gauge,
  GitBranch,
  LayoutDashboard,
  ListChecks,
  Loader2,
  LogOut,
  LucideIcon,
  Play,
  Plus,
  Save,
  ScanLine,
  Settings,
  RefreshCw,
  Rocket,
  ShieldCheck,
  Square,
  Timer,
  UserCheck,
  UserPlus,
  UsersRound,
  Workflow,
  XCircle
} from "lucide-react";
import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { api } from "./lib/api";
import type {
  AppNotification,
  AuditEvent,
  Bottleneck,
  DepartmentMetric,
  EmployeeMetric,
  FlowProcess,
  Organization,
  Overview,
  Recommendation,
  ReportSummary,
  RbacData,
  Session,
  SlaResponse,
  SlaPolicy,
  Stage,
  StatusColor,
  TaskItem,
  TrendPoint,
  WorkflowItem
} from "./types";

type ViewKey = "dashboard" | "processes" | "tasks" | "sla" | "analytics" | "organization" | "reports" | "admin";

interface WorkspaceData {
  overview: Overview;
  processes: FlowProcess[];
  workflows: WorkflowItem[];
  tasks: TaskItem[];
  sla: SlaResponse;
  bottlenecks: Bottleneck[];
  recommendations: Recommendation[];
  organization: Organization;
  notifications: AppNotification[];
  rbac: RbacData;
  audit: AuditEvent[];
  report: ReportSummary;
  slaPolicies: SlaPolicy[];
}

const storageKey = "flowops-session";

const navigation: Array<{ id: ViewKey; label: string; icon: LucideIcon }> = [
  { id: "dashboard", label: "Executive", icon: LayoutDashboard },
  { id: "processes", label: "Processes", icon: GitBranch },
  { id: "tasks", label: "Tasks", icon: ListChecks },
  { id: "sla", label: "SLA", icon: Gauge },
  { id: "analytics", label: "Analytics", icon: Activity },
  { id: "organization", label: "Organization", icon: Building2 },
  { id: "reports", label: "Reports", icon: FileBarChart },
  { id: "admin", label: "Administration", icon: Settings }
];

function readSession(): Session | null {
  const raw = localStorage.getItem(storageKey);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as Session;
  } catch {
    localStorage.removeItem(storageKey);
    return null;
  }
}

function saveSession(session: Session | null) {
  if (session) {
    localStorage.setItem(storageKey, JSON.stringify(session));
  } else {
    localStorage.removeItem(storageKey);
  }
}

function formatDate(value: string | null) {
  if (!value) return "Not yet";
  return new Intl.DateTimeFormat("en", { month: "short", day: "2-digit" }).format(new Date(value));
}

function formatNumber(value: number, suffix = "") {
  return `${new Intl.NumberFormat("en", { maximumFractionDigits: 1 }).format(value)}${suffix}`;
}

function friendlyError(error: unknown) {
  if (error instanceof Error) {
    try {
      const parsed = JSON.parse(error.message) as { detail?: string };
      return parsed.detail ?? error.message;
    } catch {
      return error.message;
    }
  }
  return "Unexpected error";
}

export default function App() {
  const [session, setSession] = useState<Session | null>(() => readSession());
  const [workspace, setWorkspace] = useState<WorkspaceData | null>(null);
  const [activeView, setActiveView] = useState<ViewKey>("dashboard");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadWorkspace = useCallback(async () => {
    if (!session) return;
    setLoading(true);
    setError(null);
    try {
      const token = session.access_token;
      const [
        overview,
        processes,
        workflows,
        tasks,
        sla,
        bottlenecks,
        recommendations,
        organization,
        notifications,
        rbac,
        audit,
        report,
        slaPolicies
      ] = await Promise.all([
        api.overview(token),
        api.processes(token),
        api.workflows(token),
        api.tasks(token),
        api.sla(token),
        api.bottlenecks(token),
        api.recommendations(token),
        api.organization(token),
        api.notifications(token),
        api.rbac(token),
        api.audit(token),
        api.reports(token),
        api.slaPolicies(token)
      ]);
      setWorkspace({ overview, processes, workflows, tasks, sla, bottlenecks, recommendations, organization, notifications, rbac, audit, report, slaPolicies });
    } catch (caught) {
      setError(friendlyError(caught));
    } finally {
      setLoading(false);
    }
  }, [session]);

  useEffect(() => {
    void loadWorkspace();
  }, [loadWorkspace]);

  function handleLogin(nextSession: Session) {
    saveSession(nextSession);
    setSession(nextSession);
  }

  function handleLogout() {
    saveSession(null);
    setSession(null);
    setWorkspace(null);
  }

  if (!session) {
    return <LoginScreen onLoggedIn={handleLogin} />;
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand-lockup">
          <div className="brand-mark">
            <Workflow size={22} />
          </div>
          <div>
            <div className="brand-title">FlowOps</div>
            <div className="brand-subtitle">Process Intelligence</div>
          </div>
        </div>

        <nav className="nav-list" aria-label="Main navigation">
          {navigation.map((item) => {
            const Icon = item.icon;
            return (
              <button
                className={`nav-item ${activeView === item.id ? "active" : ""}`}
                key={item.id}
                onClick={() => setActiveView(item.id)}
                title={item.label}
              >
                <Icon size={18} />
                <span>{item.label}</span>
              </button>
            );
          })}
        </nav>

        <div className="sidebar-footer">
          <ShieldCheck size={18} />
          <div>
            <strong>{session.user.role}</strong>
            <span>{session.user.email}</span>
          </div>
        </div>
      </aside>

      <main className="workspace">
        <header className="topbar">
          <div>
            <p className="eyebrow">Business Process Intelligence</p>
            <h1>{navigation.find((item) => item.id === activeView)?.label}</h1>
          </div>
          <div className="topbar-actions">
            <button className="icon-button" onClick={loadWorkspace} disabled={loading} title="Refresh data">
              {loading ? <Loader2 className="spin" size={18} /> : <RefreshCw size={18} />}
            </button>
            <button className="notification-button" title="Notifications">
              <Bell size={18} />
              <span>{workspace?.notifications.filter((item) => !item.read).length ?? 0}</span>
            </button>
            <button className="ghost-button" onClick={handleLogout}>
              <LogOut size={17} />
              <span>Logout</span>
            </button>
          </div>
        </header>

        {error ? <div className="error-banner">{error}</div> : null}

        {!workspace ? (
          <div className="loading-panel">
            <Loader2 className="spin" size={26} />
            <span>Loading workspace</span>
          </div>
        ) : (
          <>
            {activeView === "dashboard" && <Dashboard data={workspace} onRefresh={loadWorkspace} token={session.access_token} />}
            {activeView === "processes" && (
              <ProcessDesigner
                processes={workspace.processes}
                workflows={workspace.workflows}
                organization={workspace.organization}
                token={session.access_token}
                onRefresh={loadWorkspace}
              />
            )}
            {activeView === "tasks" && (
              <TaskManagement tasks={workspace.tasks} organization={workspace.organization} token={session.access_token} onRefresh={loadWorkspace} />
            )}
            {activeView === "sla" && (
              <SlaManagement
                sla={workspace.sla}
                policies={workspace.slaPolicies}
                processes={workspace.processes}
                token={session.access_token}
                onRefresh={loadWorkspace}
              />
            )}
            {activeView === "analytics" && (
              <Analytics bottlenecks={workspace.bottlenecks} recommendations={workspace.recommendations} />
            )}
            {activeView === "organization" && (
              <OrganizationView
                organization={workspace.organization}
                rbac={workspace.rbac}
                token={session.access_token}
                onRefresh={loadWorkspace}
              />
            )}
            {activeView === "reports" && <ReportsView report={workspace.report} token={session.access_token} />}
            {activeView === "admin" && (
              <AdminView rbac={workspace.rbac} audit={workspace.audit} token={session.access_token} onRefresh={loadWorkspace} />
            )}
          </>
        )}
      </main>
    </div>
  );
}

function LoginScreen({ onLoggedIn }: { onLoggedIn: (session: Session) => void }) {
  const [email, setEmail] = useState("admin@flowops.vn");
  const [password, setPassword] = useState("FlowOps@123");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const session = await api.login(email, password);
      onLoggedIn(session);
    } catch (caught) {
      setError(friendlyError(caught));
    } finally {
      setBusy(false);
    }
  }

  async function forgotPassword() {
    setBusy(true);
    setError(null);
    try {
      const result = await api.forgotPassword(email);
      setNotice(result.reset_token ? `${result.message} Demo token: ${result.reset_token.slice(0, 8)}...` : result.message);
    } catch (caught) {
      setError(friendlyError(caught));
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="login-page">
      <section className="login-visual" aria-label="FlowOps process canvas">
        <div className="process-lane">
          {["Apply", "Screen", "Interview", "Offer", "Onboard"].map((step, index) => (
            <div className="lane-node" key={step}>
              <span>{index + 1}</span>
              <strong>{step}</strong>
            </div>
          ))}
        </div>
        <div className="signal-strip">
          <div>
            <Timer size={18} />
            <strong>92%</strong>
            <span>SLA compliance</span>
          </div>
          <div>
            <Activity size={18} />
            <strong>1.8d</strong>
            <span>Average task time</span>
          </div>
          <div>
            <AlertTriangle size={18} />
            <strong>2</strong>
            <span>Delayed flows</span>
          </div>
        </div>
      </section>

      <form className="login-panel" onSubmit={submit}>
        <div className="brand-lockup login-brand">
          <div className="brand-mark">
            <Workflow size={22} />
          </div>
          <div>
            <div className="brand-title">FlowOps</div>
            <div className="brand-subtitle">Business Process Intelligence</div>
          </div>
        </div>

        <label>
          Email
          <input value={email} onChange={(event) => setEmail(event.target.value)} type="email" autoComplete="username" />
        </label>
        <label>
          Password
          <input
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            type="password"
            autoComplete="current-password"
          />
        </label>
        {error ? <div className="error-banner compact">{error}</div> : null}
        {notice ? <div className="notice-banner">{notice}</div> : null}
        <button className="primary-button" disabled={busy}>
          {busy ? <Loader2 className="spin" size={18} /> : <ShieldCheck size={18} />}
          <span>Login</span>
        </button>
        <button className="text-button" type="button" onClick={() => void forgotPassword()} disabled={busy}>
          Forgot password
        </button>
      </form>
    </main>
  );
}

function Dashboard({ data, token, onRefresh }: { data: WorkspaceData; token: string; onRefresh: () => Promise<void> }) {
  const metrics = data.overview.executive;
  return (
    <div className="content-stack">
      <section className="metric-grid">
        <MetricCard label="Processes" value={metrics.process_count} icon={GitBranch} accent="ink" />
        <MetricCard label="Running" value={metrics.running_processes} icon={Play} accent="blue" />
        <MetricCard label="Delayed" value={metrics.delayed_processes} icon={AlertTriangle} accent="red" />
        <MetricCard label="SLA Rate" value={formatNumber(metrics.sla_compliance_rate, "%")} icon={Gauge} accent="green" />
        <MetricCard label="Avg Time" value={formatNumber(metrics.average_processing_time_days, "d")} icon={Timer} accent="amber" />
      </section>

      <section className="two-column">
        <div className="panel">
          <PanelHeader icon={Activity} title="Weekly Throughput" />
          <TrendBars trend={data.overview.trend} />
        </div>
        <NotificationPanel notifications={data.notifications} token={token} onRefresh={onRefresh} />
      </section>

      <section className="two-column wide-left">
        <div className="panel">
          <PanelHeader icon={Building2} title="Department KPI" />
          <DepartmentTable rows={data.overview.departments} />
        </div>
        <div className="panel">
          <PanelHeader icon={Workflow} title="Workflow Instances" />
          <div className="workflow-list">
            {data.overview.workflows.map((workflow) => (
              <div className="workflow-row" key={workflow.id}>
                <div>
                  <strong>{workflow.title}</strong>
                  <span>{workflow.process_name}</span>
                </div>
                <StatusPill status={workflow.status} />
                <span>{workflow.cycle_time_days}d</span>
              </div>
            ))}
          </div>
        </div>
      </section>
    </div>
  );
}

function MetricCard({
  label,
  value,
  icon: Icon,
  accent
}: {
  label: string;
  value: string | number;
  icon: LucideIcon;
  accent: "ink" | "blue" | "red" | "green" | "amber";
}) {
  return (
    <div className={`metric-card ${accent}`}>
      <div className="metric-icon">
        <Icon size={20} />
      </div>
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function PanelHeader({ icon: Icon, title }: { icon: LucideIcon; title: string }) {
  return (
    <div className="panel-header">
      <Icon size={18} />
      <h2>{title}</h2>
    </div>
  );
}

function TrendBars({ trend }: { trend: TrendPoint[] }) {
  const max = Math.max(...trend.map((point) => point.completed + point.delayed), 1);
  return (
    <div className="trend-bars">
      {trend.map((point) => (
        <div className="trend-column" key={point.day}>
          <div className="trend-track">
            <div className="trend-completed" style={{ height: `${(point.completed / max) * 100}%` }} />
            <div className="trend-delayed" style={{ height: `${(point.delayed / max) * 100}%` }} />
          </div>
          <span>{point.day}</span>
        </div>
      ))}
    </div>
  );
}

function NotificationPanel({
  notifications,
  token,
  onRefresh
}: {
  notifications: AppNotification[];
  token: string;
  onRefresh: () => Promise<void>;
}) {
  async function markRead(id: string) {
    await api.markNotificationRead(token, id);
    await onRefresh();
  }

  async function markAllRead() {
    await api.markAllNotificationsRead(token);
    await onRefresh();
  }

  return (
    <div className="panel">
      <PanelHeader icon={Bell} title="Notifications" />
      <button className="text-button panel-action" onClick={() => void markAllRead()}>
        Mark all read
      </button>
      <div className="notification-list">
        {notifications.slice(0, 5).map((notification) => (
          <button
            className={`notification-row ${notification.read ? "" : "unread"}`}
            key={notification.id}
            onClick={() => void markRead(notification.id)}
          >
            <span>{notification.type}</span>
            <strong>{notification.title}</strong>
            <small>{formatDate(notification.created_at)}</small>
          </button>
        ))}
      </div>
    </div>
  );
}

function DepartmentTable({ rows }: { rows: DepartmentMetric[] }) {
  return (
    <div className="data-table compact-table">
      <div className="table-row table-head">
        <span>Department</span>
        <span>Throughput</span>
        <span>Avg Time</span>
        <span>Success</span>
      </div>
      {rows.map((row) => (
        <div className="table-row" key={row.department_id}>
          <strong>{row.department}</strong>
          <span>{row.throughput}</span>
          <span>{row.average_task_time_days}d</span>
          <span>{row.process_success_rate}%</span>
        </div>
      ))}
    </div>
  );
}

function ProcessDesigner({
  processes,
  workflows,
  organization,
  token,
  onRefresh
}: {
  processes: FlowProcess[];
  workflows: WorkflowItem[];
  organization: Organization;
  token: string;
  onRefresh: () => Promise<void>;
}) {
  const [selectedId, setSelectedId] = useState(processes[0]?.id ?? "");
  const [name, setName] = useState("Vendor Evaluation");
  const [description, setDescription] = useState("Evaluate vendor request, approve budget, and create sourcing event.");
  const [departmentId, setDepartmentId] = useState(organization.departments[0]?.id ?? "");
  const [stages, setStages] = useState("Start, Intake Review, Manager Approval, Procurement Approval, End");
  const [workflowTitle, setWorkflowTitle] = useState("New vendor onboarding");
  const [busy, setBusy] = useState(false);

  const selected = processes.find((process) => process.id === selectedId) ?? processes[0];
  const published = processes.filter((process) => process.status === "Published");
  const [editName, setEditName] = useState(selected?.name ?? "");
  const [editDescription, setEditDescription] = useState(selected?.description ?? "");
  const [editDepartment, setEditDepartment] = useState(selected?.owner_department_id ?? "");
  const [editStages, setEditStages] = useState("");

  useEffect(() => {
    if (!selected) return;
    setEditName(selected.name);
    setEditDescription(selected.description);
    setEditDepartment(selected.owner_department_id);
    setEditStages(selected.stages.map((stage) => `${stage.name}|${stage.type}|${stage.sla_days}`).join("\n"));
  }, [selected]);

  async function createProcess(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    try {
      const created = await api.createProcess(token, {
        name,
        description,
        owner_department_id: departmentId,
        stages: stages
          .split(/,|\n/)
          .map((stage) => stage.trim())
          .filter(Boolean)
      });
      setSelectedId(created.id);
      await onRefresh();
    } finally {
      setBusy(false);
    }
  }

  async function publishProcess(processId: string) {
    setBusy(true);
    try {
      await api.publishProcess(token, processId);
      await onRefresh();
    } finally {
      setBusy(false);
    }
  }

  async function saveProcess(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selected) return;
    const parsedStages = editStages
      .split("\n")
      .map((row) => row.trim())
      .filter(Boolean)
      .map((row) => {
        const [stageName, stageType = "User Task", sla = "2"] = row.split("|").map((part) => part.trim());
        return { name: stageName, type: stageType, sla_days: Number(sla) || 0 };
      });
    setBusy(true);
    try {
      await api.updateProcess(token, selected.id, {
        name: editName,
        description: editDescription,
        owner_department_id: editDepartment,
        stages: parsedStages
      });
      await onRefresh();
    } finally {
      setBusy(false);
    }
  }

  async function versionProcess(processId: string) {
    setBusy(true);
    try {
      await api.versionProcess(token, processId);
      await onRefresh();
    } finally {
      setBusy(false);
    }
  }

  async function archiveProcess(processId: string) {
    setBusy(true);
    try {
      await api.archiveProcess(token, processId);
      await onRefresh();
    } finally {
      setBusy(false);
    }
  }

  async function startWorkflow(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selected) return;
    setBusy(true);
    try {
      await api.startWorkflow(token, { process_id: selected.id, title: workflowTitle });
      await onRefresh();
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="content-stack">
      <section className="process-layout">
        <div className="panel process-list-panel">
          <PanelHeader icon={GitBranch} title="Process Library" />
          <div className="process-list">
            {processes.map((process) => (
              <button
                className={`process-list-item ${selected?.id === process.id ? "active" : ""}`}
                key={process.id}
                onClick={() => setSelectedId(process.id)}
              >
                <strong>{process.name}</strong>
                <span>
                  v{process.version} - {process.owner_department}
                </span>
                <StatusPill status={process.status} />
              </button>
            ))}
          </div>
        </div>

        <div className="panel designer-panel">
          <PanelHeader icon={Workflow} title={selected?.name ?? "Process"} />
          {selected ? <BpmnCanvas process={selected} /> : null}
          <div className="designer-actions">
            <div className="row-actions">
              {selected?.status === "Draft" ? (
                <button className="secondary-button" onClick={() => void publishProcess(selected.id)} disabled={busy}>
                  <Rocket size={17} />
                  <span>Publish</span>
                </button>
              ) : null}
              {selected?.status === "Published" ? (
                <button className="secondary-button" onClick={() => void versionProcess(selected.id)} disabled={busy}>
                  <RefreshCw size={17} />
                  <span>New version</span>
                </button>
              ) : null}
              {selected?.status !== "Archived" ? (
                <button className="ghost-button" onClick={() => void archiveProcess(selected.id)} disabled={busy}>
                  <Archive size={17} />
                  <span>Archive</span>
                </button>
              ) : null}
            </div>
            <span>{selected?.instance_count ?? 0} workflow instances</span>
          </div>
        </div>
      </section>

      {selected && selected.status !== "Archived" ? (
        <form className="panel process-editor" onSubmit={saveProcess}>
          <PanelHeader icon={Save} title="Process Editor" />
          <div className="process-editor-grid">
            <label>
              Name
              <input value={editName} onChange={(event) => setEditName(event.target.value)} />
            </label>
            <label>
              Owner Department
              <select value={editDepartment} onChange={(event) => setEditDepartment(event.target.value)}>
                {organization.departments.map((department) => (
                  <option key={department.id} value={department.id}>{department.name}</option>
                ))}
              </select>
            </label>
            <label className="span-two">
              Description
              <input value={editDescription} onChange={(event) => setEditDescription(event.target.value)} />
            </label>
            <label className="span-two">
              BPMN stages: name | type | SLA days
              <textarea value={editStages} onChange={(event) => setEditStages(event.target.value)} rows={5} />
            </label>
          </div>
          <button className="primary-button" disabled={busy}>
            {busy ? <Loader2 className="spin" size={18} /> : <Save size={18} />}
            <span>Save draft</span>
          </button>
        </form>
      ) : null}

      <section className="two-column">
        <form className="panel form-panel" onSubmit={createProcess}>
          <PanelHeader icon={Plus} title="Create Process" />
          <label>
            Name
            <input value={name} onChange={(event) => setName(event.target.value)} />
          </label>
          <label>
            Description
            <textarea value={description} onChange={(event) => setDescription(event.target.value)} rows={3} />
          </label>
          <label>
            Owner Department
            <select value={departmentId} onChange={(event) => setDepartmentId(event.target.value)}>
              {organization.departments.map((department) => (
                <option key={department.id} value={department.id}>
                  {department.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            Stages
            <textarea value={stages} onChange={(event) => setStages(event.target.value)} rows={3} />
          </label>
          <button className="primary-button" disabled={busy}>
            {busy ? <Loader2 className="spin" size={18} /> : <Plus size={18} />}
            <span>Create</span>
          </button>
        </form>

        <form className="panel form-panel" onSubmit={startWorkflow}>
          <PanelHeader icon={Play} title="Start Workflow" />
          <label>
            Published Process
            <select value={selected?.id ?? ""} onChange={(event) => setSelectedId(event.target.value)}>
              {published.map((process) => (
                <option key={process.id} value={process.id}>
                  {process.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            Title
            <input value={workflowTitle} onChange={(event) => setWorkflowTitle(event.target.value)} />
          </label>
          <button className="primary-button" disabled={busy || !selected || selected.status !== "Published"}>
            {busy ? <Loader2 className="spin" size={18} /> : <Play size={18} />}
            <span>Start</span>
          </button>
          <div className="workflow-list slim">
            {workflows.slice(0, 4).map((workflow) => (
              <div className="workflow-row" key={workflow.id}>
                <strong>{workflow.title}</strong>
                <StatusPill status={workflow.status} />
              </div>
            ))}
          </div>
        </form>
      </section>
    </div>
  );
}

function BpmnCanvas({ process }: { process: FlowProcess }) {
  return (
    <div className="bpmn-canvas">
      {process.stages.map((stage, index) => (
        <div className="bpmn-step-wrap" key={stage.id}>
          <StageNode stage={stage} />
          {index < process.stages.length - 1 ? <div className="connector" /> : null}
        </div>
      ))}
    </div>
  );
}

function StageNode({ stage }: { stage: Stage }) {
  const Icon = stage.type.includes("Gateway")
    ? Diamond
    : stage.type.includes("Start") || stage.type.includes("End")
      ? Circle
      : stage.type.includes("Service")
        ? Square
        : UserCheck;
  return (
    <div className={`stage-node ${stage.type.includes("Gateway") ? "gateway" : ""}`}>
      <Icon size={18} />
      <strong>{stage.name}</strong>
      <span>{stage.sla_days ? `${stage.sla_days}d SLA` : stage.type}</span>
    </div>
  );
}

function TaskManagement({
  tasks,
  organization,
  token,
  onRefresh
}: {
  tasks: TaskItem[];
  organization: Organization;
  token: string;
  onRefresh: () => Promise<void>;
}) {
  const [filter, setFilter] = useState<"All" | TaskItem["status"]>("All");
  const [busyTask, setBusyTask] = useState<string | null>(null);
  const visibleTasks = useMemo(
    () => (filter === "All" ? tasks : tasks.filter((task) => task.status === filter)),
    [filter, tasks]
  );

  async function runTaskAction(
    taskId: string,
    action: "claim" | "assign" | "reassign" | "start" | "complete" | "reject" | "cancel" | "escalate",
    assignee_id?: string
  ) {
    setBusyTask(taskId);
    try {
      await api.taskAction(token, taskId, { action, assignee_id });
      await onRefresh();
    } finally {
      setBusyTask(null);
    }
  }

  return (
    <div className="content-stack">
      <section className="toolbar-row">
        {(["All", "Pending", "In Progress", "Completed", "Rejected", "Cancelled"] as const).map((status) => (
          <button className={`segment-button ${filter === status ? "active" : ""}`} key={status} onClick={() => setFilter(status)}>
            {status}
          </button>
        ))}
      </section>

      <section className="panel">
        <PanelHeader icon={ListChecks} title="Task Management" />
        <div className="task-table">
          <div className="task-row task-head">
            <span>Task</span>
            <span>Owner</span>
            <span>Priority</span>
            <span>SLA</span>
            <span>Due</span>
            <span>Action</span>
          </div>
          {visibleTasks.map((task) => (
            <div className="task-row" key={task.id}>
              <div>
                <strong>{task.name}</strong>
                <span>{task.process_name}</span>
              </div>
              <div>
                <strong>{task.assignee_name}</strong>
                <span>{task.department_name}</span>
              </div>
              <PriorityPill priority={task.priority} />
              <SlaPill status={task.sla.status} />
              <span>{formatDate(task.due_at)}</span>
              <div className="row-actions">
                <button
                  className="icon-button"
                  title="Claim task"
                  disabled={busyTask === task.id || !["Pending", "In Progress"].includes(task.status)}
                  onClick={() => void runTaskAction(task.id, "claim")}
                >
                  {busyTask === task.id ? <Loader2 className="spin" size={16} /> : <UserCheck size={16} />}
                </button>
                <button
                  className="icon-button"
                  title={task.status === "Pending" ? "Start task" : "Complete task"}
                  disabled={busyTask === task.id || !["Pending", "In Progress"].includes(task.status)}
                  onClick={() => void runTaskAction(task.id, task.status === "Pending" ? "start" : "complete")}
                >
                  {task.status === "Pending" ? <Play size={16} /> : <CheckCircle2 size={16} />}
                </button>
                <button
                  className="icon-button danger"
                  title="Reject task"
                  disabled={busyTask === task.id || !["Pending", "In Progress"].includes(task.status)}
                  onClick={() => void runTaskAction(task.id, "reject")}
                >
                  <XCircle size={16} />
                </button>
                <button
                  className="icon-button warning"
                  title="Escalate task"
                  disabled={busyTask === task.id || !["Pending", "In Progress"].includes(task.status)}
                  onClick={() => void runTaskAction(task.id, "escalate")}
                >
                  <ArrowUpCircle size={16} />
                </button>
                <select
                  aria-label="Assignee"
                  value={task.assignee_id}
                  disabled={!["Pending", "In Progress"].includes(task.status)}
                  onChange={(event) => void runTaskAction(task.id, "reassign", event.target.value)}
                >
                  {organization.employees.map((employee) => (
                    <option value={employee.id} key={employee.id}>
                      {employee.name}
                    </option>
                  ))}
                </select>
              </div>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}

function SlaManagement({
  sla,
  policies,
  processes,
  token,
  onRefresh
}: {
  sla: SlaResponse;
  policies: SlaPolicy[];
  processes: FlowProcess[];
  token: string;
  onRefresh: () => Promise<void>;
}) {
  const initialProcess = processes[0];
  const [processId, setProcessId] = useState(initialProcess?.id ?? "");
  const process = processes.find((item) => item.id === processId) ?? initialProcess;
  const executableStages = process?.stages.filter((stage) => ["Task", "User Task", "Service Task"].includes(stage.type)) ?? [];
  const [stageId, setStageId] = useState(executableStages[0]?.id ?? "");
  const existingPolicy = policies.find((policy) => policy.process_id === processId && policy.stage_id === stageId);
  const [targetHours, setTargetHours] = useState(existingPolicy?.target_hours ?? 48);
  const [warningPercent, setWarningPercent] = useState(existingPolicy?.warning_percent ?? 80);
  const [escalationRole, setEscalationRole] = useState(existingPolicy?.escalation_role ?? "Manager");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    const firstStage = processes.find((item) => item.id === processId)?.stages.find((stage) => ["Task", "User Task", "Service Task"].includes(stage.type));
    if (firstStage && !executableStages.some((stage) => stage.id === stageId)) setStageId(firstStage.id);
  }, [executableStages, processId, processes, stageId]);

  useEffect(() => {
    if (!existingPolicy) return;
    setTargetHours(existingPolicy.target_hours);
    setWarningPercent(existingPolicy.warning_percent);
    setEscalationRole(existingPolicy.escalation_role);
  }, [existingPolicy]);

  async function savePolicy(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const payload = {
      process_id: processId,
      stage_id: stageId,
      target_hours: targetHours,
      warning_percent: warningPercent,
      escalation_role: escalationRole,
      active: true
    };
    setBusy(true);
    try {
      if (existingPolicy) await api.updateSlaPolicy(token, existingPolicy.id, payload);
      else await api.createSlaPolicy(token, payload);
      await onRefresh();
    } finally {
      setBusy(false);
    }
  }

  async function scanBreaches() {
    setBusy(true);
    try {
      await api.scanSla(token);
      await onRefresh();
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="content-stack">
      <section className="metric-grid three">
        <MetricCard label="Within SLA" value={sla.summary.green} icon={CheckCircle2} accent="green" />
        <MetricCard label="80% Consumed" value={sla.summary.yellow} icon={Timer} accent="amber" />
        <MetricCard label="Violated" value={sla.summary.red} icon={AlertTriangle} accent="red" />
      </section>
      <section className="two-column">
        <form className="panel form-panel" onSubmit={savePolicy}>
          <PanelHeader icon={Gauge} title="SLA Policy" />
          <label>
            Process
            <select value={processId} onChange={(event) => setProcessId(event.target.value)}>
              {processes.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
            </select>
          </label>
          <label>
            Stage
            <select value={stageId} onChange={(event) => setStageId(event.target.value)}>
              {executableStages.map((stage) => <option key={stage.id} value={stage.id}>{stage.name}</option>)}
            </select>
          </label>
          <div className="form-grid-three">
            <label>
              Target hours
              <input type="number" min="1" value={targetHours} onChange={(event) => setTargetHours(Number(event.target.value))} />
            </label>
            <label>
              Warning %
              <input type="number" min="1" max="100" value={warningPercent} onChange={(event) => setWarningPercent(Number(event.target.value))} />
            </label>
            <label>
              Escalation role
              <select value={escalationRole} onChange={(event) => setEscalationRole(event.target.value)}>
                <option>Manager</option>
                <option>Process Manager</option>
                <option>Admin</option>
              </select>
            </label>
          </div>
          <button className="primary-button" disabled={busy || !stageId}>
            <Save size={18} />
            <span>{existingPolicy ? "Update policy" : "Create policy"}</span>
          </button>
        </form>
        <div className="panel">
          <PanelHeader icon={ScanLine} title="Escalation Rules" />
          <div className="policy-list">
            {policies.slice(0, 8).map((policy) => (
              <button className="policy-row" key={policy.id} onClick={() => { setProcessId(policy.process_id); setStageId(policy.stage_id); }}>
                <div><strong>{policy.stage_name}</strong><span>{policy.process_name}</span></div>
                <span>{policy.target_hours}h</span>
                <span>{policy.warning_percent}%</span>
              </button>
            ))}
          </div>
          <button className="secondary-button panel-action" onClick={() => void scanBreaches()} disabled={busy}>
            <ScanLine size={17} />
            <span>Scan breaches</span>
          </button>
        </div>
      </section>
      <section className="panel">
        <PanelHeader icon={Gauge} title="SLA Monitor" />
        <div className="sla-list">
          {sla.items.map((item) => (
            <div className="sla-row" key={item.id}>
              <div>
                <strong>{item.name}</strong>
                <span>{item.assignee_name} - {item.process_name}</span>
              </div>
              <div className="sla-meter" aria-label={`${item.sla.consumed_percent}% consumed`}>
                <div className={`sla-fill ${item.sla.status.toLowerCase()}`} style={{ width: `${item.sla.consumed_percent}%` }} />
              </div>
              <SlaPill status={item.sla.status} />
              <span>{item.sla.remaining_hours > 0 ? `${item.sla.remaining_hours}h left` : `${Math.abs(item.sla.remaining_hours)}h late`}</span>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}

function Analytics({
  bottlenecks,
  recommendations
}: {
  bottlenecks: Bottleneck[];
  recommendations: Recommendation[];
}) {
  return (
    <div className="content-stack">
      <section className="analytics-grid">
        {bottlenecks.map((item) => (
          <div className={`bottleneck-panel ${item.severity.toLowerCase()}`} key={`${item.process}-${item.stage}`}>
            <div className="bottleneck-header">
              <SlaPill status={item.severity === "High" ? "Red" : item.severity === "Medium" ? "Yellow" : "Green"} />
              <span>{item.process}</span>
            </div>
            <h2>{item.stage}</h2>
            <div className="bottleneck-metrics">
              <MetricMini label="Waiting" value={`${item.average_waiting_days}d`} />
              <MetricMini label="Delays" value={`${item.total_delays_percent}%`} />
              <MetricMini label="Queue" value={`${item.queue_time_days}d`} />
              <MetricMini label="Idle" value={`${item.idle_time_days}d`} />
            </div>
            <p>{item.root_cause}</p>
          </div>
        ))}
      </section>

      <section className="panel">
        <PanelHeader icon={Rocket} title="Recommendations" />
        <div className="recommendation-list">
          {recommendations.map((item) => (
            <div className="recommendation-row" key={item.id}>
              <div>
                <span>{item.rule}</span>
                <strong>{item.recommendation}</strong>
                <small>{item.impact}</small>
              </div>
              <PriorityPill priority={item.priority} />
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}

function MetricMini({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function OrganizationView({
  organization,
  rbac,
  token,
  onRefresh
}: {
  organization: Organization;
  rbac: RbacData;
  token: string;
  onRefresh: () => Promise<void>;
}) {
  const [mode, setMode] = useState<"department" | "team" | "position" | "employee">("department");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [departmentId, setDepartmentId] = useState(organization.departments[0]?.id ?? "");
  const [teamId, setTeamId] = useState(organization.teams[0]?.id ?? "");
  const [positionId, setPositionId] = useState(organization.positions[0]?.id ?? "");
  const [role, setRole] = useState(rbac.roles[0]?.name ?? "Employee");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    const firstTeam = organization.teams.find((team) => team.department_id === departmentId);
    const firstPosition = organization.positions.find((position) => position.department_id === departmentId);
    if (firstTeam) setTeamId(firstTeam.id);
    if (firstPosition) setPositionId(firstPosition.id);
  }, [departmentId, organization.positions, organization.teams]);

  async function createEntity(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    try {
      if (mode === "department") await api.createDepartment(token, { name });
      if (mode === "team") await api.createTeam(token, { name, department_id: departmentId });
      if (mode === "position") await api.createPosition(token, { name, department_id: departmentId });
      if (mode === "employee") {
        await api.createEmployee(token, {
          name,
          email,
          role,
          department_id: departmentId,
          team_id: teamId,
          position_id: positionId
        });
      }
      setName("");
      setEmail("");
      await onRefresh();
    } finally {
      setBusy(false);
    }
  }

  async function assignManager(departmentIdValue: string, managerId: string) {
    await api.assignDepartmentManager(token, departmentIdValue, managerId);
    await onRefresh();
  }

  return (
    <div className="content-stack">
      <section className="department-grid">
        {organization.departments.map((department) => {
          const employees = organization.employees.filter((employee) => employee.department_id === department.id);
          return (
            <div className="department-panel" key={department.id}>
              <Building2 size={20} />
              <h2>{department.name}</h2>
              <span>{employees.length} employees</span>
              <strong>{employees.find((employee) => employee.id === department.manager_id)?.name ?? "No manager"}</strong>
              <select
                aria-label={`Manager for ${department.name}`}
                value={department.manager_id ?? ""}
                onChange={(event) => void assignManager(department.id, event.target.value)}
              >
                <option value="" disabled>Assign manager</option>
                {organization.employees.map((employee) => <option key={employee.id} value={employee.id}>{employee.name}</option>)}
              </select>
            </div>
          );
        })}
      </section>

      <form className="panel form-panel" onSubmit={createEntity}>
        <PanelHeader icon={UserPlus} title="Organization Management" />
        <div className="toolbar-row">
          {(["department", "team", "position", "employee"] as const).map((item) => (
            <button className={`segment-button ${mode === item ? "active" : ""}`} type="button" key={item} onClick={() => setMode(item)}>
              {item[0].toUpperCase() + item.slice(1)}
            </button>
          ))}
        </div>
        <div className="organization-form-grid">
          <label>
            Name
            <input value={name} onChange={(event) => setName(event.target.value)} required />
          </label>
          {mode === "employee" ? (
            <label>
              Email
              <input type="email" value={email} onChange={(event) => setEmail(event.target.value)} required />
            </label>
          ) : null}
          {mode !== "department" ? (
            <label>
              Department
              <select value={departmentId} onChange={(event) => setDepartmentId(event.target.value)}>
                {organization.departments.map((department) => <option key={department.id} value={department.id}>{department.name}</option>)}
              </select>
            </label>
          ) : null}
          {mode === "employee" ? (
            <>
              <label>
                Team
                <select value={teamId} onChange={(event) => setTeamId(event.target.value)}>
                  {organization.teams.filter((team) => team.department_id === departmentId).map((team) => <option key={team.id} value={team.id}>{team.name}</option>)}
                </select>
              </label>
              <label>
                Position
                <select value={positionId} onChange={(event) => setPositionId(event.target.value)}>
                  {organization.positions.filter((position) => position.department_id === departmentId).map((position) => <option key={position.id} value={position.id}>{position.name}</option>)}
                </select>
              </label>
              <label>
                Role
                <select value={role} onChange={(event) => setRole(event.target.value)}>
                  {rbac.roles.map((item) => <option key={item.id} value={item.name}>{item.name}</option>)}
                </select>
              </label>
            </>
          ) : null}
        </div>
        <button className="primary-button" disabled={busy || !name}>
          {busy ? <Loader2 className="spin" size={18} /> : <Plus size={18} />}
          <span>Create {mode}</span>
        </button>
      </form>

      <section className="panel">
        <PanelHeader icon={UsersRound} title="Employees" />
        <div className="employee-table">
          <div className="employee-row employee-head">
            <span>Name</span>
            <span>Role</span>
            <span>Department</span>
            <span>Manager</span>
          </div>
          {organization.employees.map((employee) => (
            <div className="employee-row" key={employee.id}>
              <div>
                <strong>{employee.name}</strong>
                <span>{employee.email}</span>
              </div>
              <span>{employee.role}</span>
              <span>{employee.department_name}</span>
              <span>{employee.manager_name}</span>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}

function ReportsView({ report, token }: { report: ReportSummary; token: string }) {
  const [busy, setBusy] = useState(false);

  async function downloadReport() {
    setBusy(true);
    try {
      const blob = await api.downloadReport(token);
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = "flowops-report.csv";
      anchor.click();
      URL.revokeObjectURL(url);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="content-stack">
      <section className="toolbar-row report-toolbar">
        <span>Generated {formatDate(report.generated_at)}</span>
        <button className="primary-button" onClick={() => void downloadReport()} disabled={busy}>
          {busy ? <Loader2 className="spin" size={18} /> : <Download size={18} />}
          <span>Export CSV</span>
        </button>
      </section>
      <section className="panel">
        <PanelHeader icon={FileBarChart} title="Business Objectives" />
        <div className="report-metric-grid">
          {report.objectives.map((metric) => (
            <div className="report-metric" key={metric.id}>
              <span>{metric.id}</span>
              <strong>{metric.name}</strong>
              <div className="report-progress"><div style={{ width: `${Math.min((metric.actual / metric.target) * 100, 100)}%` }} /></div>
              <small>{metric.actual}{metric.unit} / {metric.target}{metric.unit}</small>
            </div>
          ))}
        </div>
      </section>
      <section className="two-column">
        <div className="panel">
          <PanelHeader icon={Gauge} title="Success Metrics" />
          <div className="success-metric-list">
            {report.success_metrics.map((metric) => (
              <div className="success-metric-row" key={metric.name}>
                <div><strong>{metric.name}</strong><span>Target {metric.target}{metric.unit}</span></div>
                <strong>{metric.actual}{metric.unit}</strong>
                <StatusPill status={metric.actual >= metric.target ? "Completed" : "In Progress"} />
              </div>
            ))}
          </div>
        </div>
        <div className="panel">
          <PanelHeader icon={UsersRound} title="Employee KPI" />
          <EmployeeKpiTable rows={report.employees} />
        </div>
      </section>
    </div>
  );
}

function EmployeeKpiTable({ rows }: { rows: EmployeeMetric[] }) {
  return (
    <div className="employee-kpi-list">
      {rows.map((row) => (
        <div className="employee-kpi-row" key={row.employee_id}>
          <div><strong>{row.employee}</strong><span>{row.department}</span></div>
          <span>{row.completed_tasks}/{row.assigned_tasks}</span>
          <span className={row.overdue_tasks ? "text-danger" : "text-success"}>{row.overdue_tasks} overdue</span>
        </div>
      ))}
    </div>
  );
}

function AdminView({
  rbac,
  audit,
  token,
  onRefresh
}: {
  rbac: RbacData;
  audit: AuditEvent[];
  token: string;
  onRefresh: () => Promise<void>;
}) {
  const [roleName, setRoleName] = useState("");
  const [permissions, setPermissions] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);

  function toggleNewPermission(permission: string) {
    setPermissions((current) => current.includes(permission) ? current.filter((item) => item !== permission) : [...current, permission]);
  }

  async function createRole(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    try {
      await api.createRole(token, { name: roleName, permissions });
      setRoleName("");
      setPermissions([]);
      await onRefresh();
    } finally {
      setBusy(false);
    }
  }

  async function toggleRolePermission(role: RbacData["roles"][number], permission: string) {
    const next = role.permissions.includes(permission)
      ? role.permissions.filter((item) => item !== permission)
      : [...role.permissions, permission];
    await api.updateRole(token, role.id, { name: role.name, permissions: next });
    await onRefresh();
  }

  return (
    <div className="content-stack">
      <form className="panel form-panel" onSubmit={createRole}>
        <PanelHeader icon={ShieldCheck} title="Roles and Permissions" />
        <label>
          Role name
          <input value={roleName} onChange={(event) => setRoleName(event.target.value)} required />
        </label>
        <div className="permission-grid">
          {rbac.permissions.map((permission) => (
            <label className="permission-check" key={permission}>
              <input type="checkbox" checked={permissions.includes(permission)} onChange={() => toggleNewPermission(permission)} />
              <span>{permission}</span>
            </label>
          ))}
        </div>
        <button className="primary-button" disabled={busy || !roleName}>
          <Plus size={18} />
          <span>Create role</span>
        </button>
      </form>

      <section className="panel">
        <PanelHeader icon={ShieldCheck} title="Permission Matrix" />
        <div className="role-list">
          {rbac.roles.map((role) => (
            <div className="role-row" key={role.id}>
              <div><strong>{role.name}</strong><span>{role.permissions.length} permissions</span></div>
              <div className="permission-pills">
                {rbac.permissions.map((permission) => (
                  <button
                    className={`permission-pill ${role.permissions.includes(permission) ? "active" : ""}`}
                    key={permission}
                    onClick={() => void toggleRolePermission(role, permission)}
                    title={`${role.permissions.includes(permission) ? "Remove" : "Add"} ${permission}`}
                  >
                    {permission}
                  </button>
                ))}
              </div>
            </div>
          ))}
        </div>
      </section>

      <section className="panel">
        <PanelHeader icon={Activity} title="Audit Log" />
        <div className="audit-list">
          {audit.slice(0, 40).map((event) => (
            <div className="audit-row" key={event.id}>
              <span>{formatDate(event.created_at)}</span>
              <strong>{event.actor_name}</strong>
              <span>{event.action}</span>
              <StatusPill status={event.entity_type ?? "system"} />
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}

function SlaPill({ status }: { status: StatusColor }) {
  return <span className={`pill sla-${status.toLowerCase()}`}>{status}</span>;
}

function StatusPill({ status }: { status: string }) {
  return <span className={`pill status-${status.toLowerCase().replace(/\s/g, "-")}`}>{status}</span>;
}

function PriorityPill({ priority }: { priority: string }) {
  return <span className={`pill priority-${priority.toLowerCase()}`}>{priority}</span>;
}
