export type StatusColor = "Green" | "Yellow" | "Red";

export interface User {
  id: string;
  name: string;
  email: string;
  role: string;
  department_id: string;
}

export interface Session {
  access_token: string;
  refresh_token: string;
  token_type: "bearer";
  user: User;
}

export interface Stage {
  id: string;
  name: string;
  type: string;
  sla_days: number;
}

export interface ProcessVersion {
  id: string;
  process_id: string;
  version: number;
  status: string;
  created_at: string;
  created_by: string;
}

export interface FlowProcess {
  id: string;
  name: string;
  description: string;
  status: "Draft" | "Published" | "Archived";
  version: number;
  owner_department_id: string;
  owner_department: string;
  instance_count: number;
  stages: Stage[];
  created_at: string;
  updated_at?: string;
  versions?: ProcessVersion[];
}

export interface WorkflowItem {
  id: string;
  process_id: string;
  process_name: string;
  title: string;
  requester_id: string;
  requester_name: string;
  status: string;
  current_stage: string;
  started_at: string;
  completed_at: string | null;
  cycle_time_days: number;
}

export interface SlaState {
  status: StatusColor;
  consumed_percent: number;
  remaining_hours: number;
  breached: boolean;
}

export interface TaskItem {
  id: string;
  workflow_id: string;
  process_id: string;
  process_name: string;
  stage_id: string;
  name: string;
  assignee_id: string;
  assignee_name: string;
  department_id: string;
  department_name: string;
  priority: "Low" | "Medium" | "High" | "Critical";
  status: "Pending" | "In Progress" | "Completed" | "Rejected" | "Cancelled";
  created_at: string;
  due_at: string;
  completed_at: string | null;
  sla: SlaState;
  escalation_count?: number;
}

export interface ExecutiveMetrics {
  process_count: number;
  running_processes: number;
  completed_processes: number;
  delayed_processes: number;
  average_processing_time_days: number;
  sla_compliance_rate: number;
}

export interface DepartmentMetric {
  department_id: string;
  department: string;
  throughput: number;
  average_task_time_days: number;
  employee_productivity: number;
  process_success_rate: number;
}

export interface EmployeeMetric {
  employee_id: string;
  employee: string;
  department: string;
  assigned_tasks: number;
  completed_tasks: number;
  overdue_tasks: number;
  average_completion_time_days: number;
}

export interface TrendPoint {
  day: string;
  completed: number;
  delayed: number;
}

export interface Overview {
  executive: ExecutiveMetrics;
  departments: DepartmentMetric[];
  employees: EmployeeMetric[];
  workflows: WorkflowItem[];
  trend: TrendPoint[];
}

export interface SlaResponse {
  summary: {
    green: number;
    yellow: number;
    red: number;
  };
  items: TaskItem[];
}

export interface Bottleneck {
  process_id: string;
  process: string;
  stage: string;
  average_waiting_days: number;
  total_delays_percent: number;
  cycle_time_days: number;
  lead_time_days: number;
  queue_time_days: number;
  throughput: number;
  idle_time_days: number;
  root_cause: string;
  severity: "Low" | "Medium" | "High";
}

export interface Recommendation {
  id: string;
  type: string;
  priority: "Low" | "Medium" | "High";
  rule: string;
  recommendation: string;
  impact: string;
}

export interface Department {
  id: string;
  name: string;
  manager_id: string | null;
}

export interface Team {
  id: string;
  name: string;
  department_id: string;
}

export interface Position {
  id: string;
  name: string;
  department_id: string;
}

export interface Employee {
  id: string;
  name: string;
  email: string;
  role: string;
  department_id: string;
  department_name: string;
  manager_name: string;
  team_id: string;
  position_id: string;
}

export interface Organization {
  departments: Department[];
  teams: Team[];
  positions: Position[];
  employees: Employee[];
}

export interface AppNotification {
  id: string;
  type: string;
  title: string;
  message: string;
  recipient_id: string | null;
  created_at: string;
  read: boolean;
}

export interface Role {
  id: string;
  name: string;
  permissions: string[];
}

export interface RbacData {
  roles: Role[];
  permissions: string[];
}

export interface SlaPolicy {
  id: string;
  process_id: string;
  process_name: string;
  stage_id: string;
  stage_name: string;
  target_hours: number;
  warning_percent: number;
  escalation_role: string;
  active: boolean;
}

export interface AuditEvent {
  id: string;
  actor_id: string;
  actor_name: string;
  action: string;
  entity_type?: string;
  entity_id?: string | null;
  created_at: string;
}

export interface ReportMetric {
  id?: string;
  name: string;
  target: number;
  actual: number;
  unit: string;
}

export interface ReportSummary {
  generated_at: string;
  executive: ExecutiveMetrics;
  objectives: ReportMetric[];
  success_metrics: ReportMetric[];
  departments: DepartmentMetric[];
  employees: EmployeeMetric[];
  bottlenecks: Bottleneck[];
  recommendations: Recommendation[];
}
