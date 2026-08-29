const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const TOKEN_KEY = "og_pios_token";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

export function hasToken(): boolean {
  if (typeof window === "undefined") return false;
  return Boolean(window.localStorage.getItem(TOKEN_KEY));
}

function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(TOKEN_KEY);
}

function clearTokenAndRedirect(): void {
  if (typeof window === "undefined") return;
  window.localStorage.removeItem(TOKEN_KEY);
  window.location.href = "/login";
}

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const token = getToken();
  const headers = new Headers(init?.headers);
  if (token) headers.set("Authorization", `Bearer ${token}`);
  // Skip for FormData bodies (e.g. file uploads) — the browser must set its own
  // multipart boundary; a manually-set Content-Type here would break it.
  if (init?.body && !headers.has("Content-Type") && !(init.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }

  const response = await fetch(`${API_URL}${path}`, { ...init, headers });

  if (response.status === 401) {
    clearTokenAndRedirect();
    throw new ApiError(401, "Session expired");
  }

  if (!response.ok) {
    const body = await response.json().catch(() => ({}) as { detail?: string });
    throw new ApiError(response.status, body.detail ?? response.statusText);
  }

  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}

function buildQuery(params: Record<string, string | number | undefined>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== "") {
      search.set(key, String(value));
    }
  }
  const qs = search.toString();
  return qs ? `?${qs}` : "";
}

// ----- Types -----

export type FieldSummary = { id: number; name: string };

export type FacilitySummary = {
  id: number;
  name: string;
  facility_type: string | null;
  field: FieldSummary;
};

export type Facility = {
  id: number;
  name: string;
  facility_type: string | null;
  field_id: number;
  field_name: string;
};

export type Well = {
  id: number;
  well_id: string;
  name: string;
  well_type: string | null;
  status: string;
  artificial_lift_type: string | null;
  latitude: number | null;
  longitude: number | null;
  completion_date: string | null;
  completion_type: string | null;
  total_depth_ft: number | null;
  facility_id: number;
  facility: FacilitySummary;
  created_at: string;
  updated_at: string;
};

export type WellListResponse = {
  items: Well[];
  total: number;
  page: number;
  page_size: number;
};

export type WellPayload = {
  well_id: string;
  name: string;
  well_type?: string | null;
  status?: string;
  artificial_lift_type?: string | null;
  latitude?: number | null;
  longitude?: number | null;
  completion_date?: string | null;
  completion_type?: string | null;
  total_depth_ft?: number | null;
  facility_id: number;
};

export type ProductionRecord = {
  id: number;
  record_date: string;
  oil_bopd: number;
  gas_mscfd: number;
  water_bwpd: number;
  water_cut_pct: number | null;
  gor: number | null;
  choke_size: number | null;
};

export type PressureRecord = {
  id: number;
  record_date: string;
  wellhead_pressure: number | null;
  tubing_pressure: number | null;
  casing_pressure: number | null;
  flowline_pressure: number | null;
};

export type DowntimeEvent = {
  id: number;
  start_time: string;
  end_time: string | null;
  reason: string | null;
};

export type DowntimeResponse = {
  events: DowntimeEvent[];
  summary: { event_count: number; total_hours: number };
};

export type MaintenanceRecord = {
  id: number;
  maintenance_type: string;
  status: string;
  description: string | null;
  start_date: string | null;
  completion_date: string | null;
  cost: number | null;
  equipment_tag: string;
  equipment_type: string;
};

export type MaintenanceResponse = {
  records: MaintenanceRecord[];
  summary: { record_count: number; total_cost: number; total_downtime_hours: number };
};

export type CurrentUser = {
  id: number;
  email: string;
  full_name: string;
  is_active: boolean;
  role_id: number;
  role_name: string;
};

// ----- Wells -----

export type ListWellsParams = {
  search?: string;
  status?: string;
  well_type?: string;
  field_id?: number;
  facility_id?: number;
  sort?: string;
  order?: "asc" | "desc";
  page?: number;
  page_size?: number;
};

export function listWells(params: ListWellsParams = {}): Promise<WellListResponse> {
  return apiFetch(`/wells${buildQuery(params)}`);
}

export function getWell(id: number): Promise<Well> {
  return apiFetch(`/wells/${id}`);
}

export function createWell(payload: WellPayload): Promise<Well> {
  return apiFetch(`/wells`, { method: "POST", body: JSON.stringify(payload) });
}

export function updateWell(id: number, payload: Partial<WellPayload>): Promise<Well> {
  return apiFetch(`/wells/${id}`, { method: "PUT", body: JSON.stringify(payload) });
}

export function getWellProduction(id: number, days = 90): Promise<ProductionRecord[]> {
  return apiFetch(`/wells/${id}/production${buildQuery({ days })}`);
}

export function getWellPressure(id: number, days = 90): Promise<PressureRecord[]> {
  return apiFetch(`/wells/${id}/pressure${buildQuery({ days })}`);
}

export function getWellDowntime(id: number): Promise<DowntimeResponse> {
  return apiFetch(`/wells/${id}/downtime`);
}

export function getWellMaintenance(id: number): Promise<MaintenanceResponse> {
  return apiFetch(`/wells/${id}/maintenance`);
}

export function listFacilities(): Promise<Facility[]> {
  return apiFetch(`/facilities`);
}

export function getCurrentUser(): Promise<CurrentUser> {
  return apiFetch(`/auth/me`);
}

export async function login(email: string, password: string): Promise<void> {
  const body = new URLSearchParams({ username: email, password });
  const response = await fetch(`${API_URL}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body,
  });
  if (!response.ok) {
    const data = await response.json().catch(() => ({}) as { detail?: string });
    throw new ApiError(response.status, data.detail ?? "Invalid email or password.");
  }
  const data = (await response.json()) as { access_token: string };
  if (typeof window !== "undefined") {
    window.localStorage.setItem(TOKEN_KEY, data.access_token);
  }
}

export function logout(): void {
  clearTokenAndRedirect();
}

export type MessageResponse = { message: string };

export function changePassword(payload: { current_password: string; new_password: string }): Promise<MessageResponse> {
  return apiFetch(`/auth/change-password`, { method: "POST", body: JSON.stringify(payload) });
}

export type ForgotPasswordResponse = {
  message: string;
  debug_token?: string | null;
  debug_reset_url?: string | null;
};

export function forgotPassword(email: string): Promise<ForgotPasswordResponse> {
  return apiFetch(`/auth/forgot-password`, { method: "POST", body: JSON.stringify({ email }) });
}

export function resetPassword(token: string, newPassword: string): Promise<MessageResponse> {
  return apiFetch(`/auth/reset-password`, {
    method: "POST",
    body: JSON.stringify({ token, new_password: newPassword }),
  });
}

export type SendVerificationResponse = {
  message: string;
  debug_token?: string | null;
  debug_verify_url?: string | null;
};

export function sendVerification(): Promise<SendVerificationResponse> {
  return apiFetch(`/auth/send-verification`, { method: "POST" });
}

export function verifyEmail(token: string): Promise<MessageResponse> {
  return apiFetch(`/auth/verify-email`, { method: "POST", body: JSON.stringify({ token }) });
}

export function listUsers(params: { role?: string } = {}): Promise<CurrentUser[]> {
  return apiFetch(`/users${buildQuery(params)}`);
}

// ----- Production -----

export type ProductionEntry = {
  id: number;
  record_date: string;
  well_id: number;
  well_code: string;
  well_name: string;
  facility_id: number;
  facility_name: string;
  field_id: number;
  field_name: string;
  oil_bopd: number;
  gas_mscfd: number;
  water_bwpd: number;
  water_cut_pct: number | null;
  gor: number | null;
  boe: number;
  choke_size: number | null;
  wellhead_pressure: number | null;
  tubing_pressure: number | null;
  casing_pressure: number | null;
  flowline_pressure: number | null;
  wellhead_temperature: number | null;
  downtime_hours: number;
  warnings: string[] | null;
};

export type ProductionListResponse = {
  items: ProductionEntry[];
  total: number;
  page: number;
  page_size: number;
};

export type ProductionPayload = {
  well_id: number;
  record_date: string;
  oil_bopd?: number;
  gas_mscfd?: number;
  water_bwpd?: number;
  choke_size?: number | null;
  wellhead_pressure?: number | null;
  tubing_pressure?: number | null;
  casing_pressure?: number | null;
  flowline_pressure?: number | null;
  wellhead_temperature?: number | null;
};

export type ListProductionParams = {
  search?: string;
  well_id?: number;
  field_id?: number;
  facility_id?: number;
  date_from?: string;
  date_to?: string;
  sort?: string;
  order?: "asc" | "desc";
  page?: number;
  page_size?: number;
};

export function listProduction(params: ListProductionParams = {}): Promise<ProductionListResponse> {
  return apiFetch(`/production${buildQuery(params)}`);
}

export function getProduction(id: number): Promise<ProductionEntry> {
  return apiFetch(`/production/${id}`);
}

export function createProduction(payload: ProductionPayload): Promise<ProductionEntry> {
  return apiFetch(`/production`, { method: "POST", body: JSON.stringify(payload) });
}

export function updateProduction(id: number, payload: Partial<ProductionPayload>): Promise<ProductionEntry> {
  return apiFetch(`/production/${id}`, { method: "PUT", body: JSON.stringify(payload) });
}

export function deleteProduction(id: number): Promise<void> {
  return apiFetch(`/production/${id}`, { method: "DELETE" });
}

export async function exportProductionCsv(params: ListProductionParams = {}): Promise<void> {
  if (typeof window === "undefined") return;
  const token = getToken();
  const headers = new Headers();
  if (token) headers.set("Authorization", `Bearer ${token}`);

  const response = await fetch(`${API_URL}/production/export${buildQuery(params)}`, { headers });
  if (!response.ok) {
    throw new ApiError(response.status, "Export failed");
  }
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = "production_export.csv";
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}

export type ProductionKpis = {
  total_oil_bbl: number;
  total_gas_mscf: number;
  total_water_bbl: number;
  avg_daily_oil_bopd: number;
  avg_daily_gas_mscfd: number;
  avg_daily_water_bwpd: number;
  avg_water_cut_pct: number | null;
  avg_gor: number | null;
  boe: number;
  boe_gas_factor: number;
  producing_wells_count: number;
  target_oil_bopd: number | null;
  target_variance_pct: number | null;
  reference_date: string | null;
  days_in_range: number;
};

export type ProductionScopeParams = {
  well_id?: number;
  field_id?: number;
  facility_id?: number;
  date_from?: string;
  date_to?: string;
};

export function getProductionKpis(params: ProductionScopeParams = {}): Promise<ProductionKpis> {
  return apiFetch(`/production/kpis${buildQuery(params)}`);
}

export type TrendMetric = "oil_gas_water" | "water_cut" | "gor" | "pressure";

export type TrendResponse = {
  metric: string;
  points: Record<string, number | string | null>[];
};

export function getProductionTrends(
  metric: TrendMetric,
  params: ProductionScopeParams = {},
): Promise<TrendResponse> {
  return apiFetch(`/production/trends${buildQuery({ metric, ...params })}`);
}

export type ScopeBar = {
  key: string;
  label: string;
  oil_bopd: number;
  gas_mscfd: number;
  water_bwpd: number;
  boe: number;
};

export type ByScopeResponse = {
  group_by: string;
  bars: ScopeBar[];
};

export function getProductionByScope(params: {
  group_by?: "well" | "field" | "facility";
  date_from?: string;
  date_to?: string;
  order?: "asc" | "desc";
  limit?: number;
}): Promise<ByScopeResponse> {
  return apiFetch(`/production/by-scope${buildQuery(params)}`);
}

export type ActualVsTargetPoint = {
  record_date: string;
  actual_oil_bopd: number;
  target_oil_bopd: number | null;
};

export function getActualVsTarget(params: ProductionScopeParams = {}): Promise<{ points: ActualVsTargetPoint[] }> {
  return apiFetch(`/production/actual-vs-target${buildQuery(params)}`);
}

export type WellIssueSummary = {
  well_id: number;
  well_code: string;
  well_name: string;
  detail: string;
};

export type ProductionIssuesResponse = {
  reference_date: string | null;
  down_wells: WellIssueSummary[];
  zero_production_wells: WellIssueSummary[];
};

export function getProductionIssues(): Promise<ProductionIssuesResponse> {
  return apiFetch(`/production/issues`);
}

// ----- Production targets -----

export type ProductionTarget = {
  id: number;
  well_id: number;
  well_code: string;
  well_name: string;
  effective_date: string;
  oil_target_bopd: number | null;
  gas_target_mscfd: number | null;
  water_target_bwpd: number | null;
};

export type ProductionTargetPayload = {
  well_id: number;
  effective_date: string;
  oil_target_bopd?: number | null;
  gas_target_mscfd?: number | null;
  water_target_bwpd?: number | null;
};

export function listProductionTargets(params: { well_id?: number } = {}): Promise<ProductionTarget[]> {
  return apiFetch(`/production/targets${buildQuery(params)}`);
}

export function createProductionTarget(payload: ProductionTargetPayload): Promise<ProductionTarget> {
  return apiFetch(`/production/targets`, { method: "POST", body: JSON.stringify(payload) });
}

export function updateProductionTarget(
  id: number,
  payload: Partial<ProductionTargetPayload>,
): Promise<ProductionTarget> {
  return apiFetch(`/production/targets/${id}`, { method: "PUT", body: JSON.stringify(payload) });
}

export function deleteProductionTarget(id: number): Promise<void> {
  return apiFetch(`/production/targets/${id}`, { method: "DELETE" });
}

// ----- Settings -----

export type SystemSetting = {
  key: string;
  value: string;
  description: string | null;
  updated_at: string;
};

export function listSettings(): Promise<SystemSetting[]> {
  return apiFetch(`/settings`);
}

export function updateSetting(key: string, value: string): Promise<SystemSetting> {
  return apiFetch(`/settings/${key}`, { method: "PUT", body: JSON.stringify({ value }) });
}

// ----- CSV import -----

export type ImportRowStatus = "valid" | "warning" | "duplicate" | "invalid";
export type ImportRowAction = "create" | "overwrite" | "skip";

export type ImportRowResult = {
  row_number: number;
  status: ImportRowStatus;
  well_id: string;
  record_date: string | null;
  parsed: Record<string, number | string | null>;
  messages: string[];
  existing_record_id: number | null;
};

export type ImportPreviewResponse = {
  total_rows: number;
  valid_count: number;
  warning_count: number;
  duplicate_count: number;
  invalid_count: number;
  rows: ImportRowResult[];
};

export type ImportConfirmRow = {
  row_number: number;
  well_id: string;
  record_date: string;
  oil_bopd?: number;
  gas_mscfd?: number;
  water_bwpd?: number;
  choke_size?: number | null;
  wellhead_pressure?: number | null;
  tubing_pressure?: number | null;
  casing_pressure?: number | null;
  flowline_pressure?: number | null;
  wellhead_temperature?: number | null;
  action: ImportRowAction;
};

export type ImportRejectedRow = {
  row_number: number;
  well_id: string;
  record_date: string;
  messages: string[];
};

export type ImportConfirmResponse = {
  created: number;
  updated: number;
  skipped: number;
  rejected: ImportRejectedRow[];
};

export function previewProductionImport(file: File): Promise<ImportPreviewResponse> {
  const formData = new FormData();
  formData.append("file", file);
  return apiFetch(`/production/import/preview`, { method: "POST", body: formData });
}

export function confirmProductionImport(rows: ImportConfirmRow[]): Promise<ImportConfirmResponse> {
  return apiFetch(`/production/import/confirm`, { method: "POST", body: JSON.stringify({ rows }) });
}

// ----- Equipment -----

export type EquipmentStatus = "operating" | "standby" | "maintenance" | "failed" | "decommissioned" | "unknown";

export type Equipment = {
  id: number;
  equipment_tag: string;
  name: string;
  equipment_type: string;
  manufacturer: string | null;
  model: string | null;
  serial_number: string | null;
  installation_date: string | null;
  commissioning_date: string | null;
  description: string | null;
  status: string;
  operating_hours: number | null;
  next_maintenance_due: string | null;
  facility_id: number | null;
  well_id: number | null;
  field_id: number | null;
  field_name: string | null;
  facility_name: string | null;
  well_code: string | null;
  health_score: number | null;
  health_band: string | null;
  last_maintenance_date: string | null;
  created_at: string;
  updated_at: string;
};

export type EquipmentListResponse = {
  items: Equipment[];
  total: number;
  page: number;
  page_size: number;
};

export type EquipmentPayload = {
  equipment_tag: string;
  name: string;
  equipment_type: string;
  manufacturer?: string | null;
  model?: string | null;
  serial_number?: string | null;
  installation_date?: string | null;
  commissioning_date?: string | null;
  description?: string | null;
  status?: EquipmentStatus;
  operating_hours?: number | null;
  next_maintenance_due?: string | null;
  facility_id?: number | null;
  well_id?: number | null;
};

export type ListEquipmentParams = {
  search?: string;
  equipment_type?: string;
  status?: string;
  field_id?: number;
  facility_id?: number;
  well_id?: number;
  sort?: string;
  order?: "asc" | "desc";
  page?: number;
  page_size?: number;
};

export function listEquipment(params: ListEquipmentParams = {}): Promise<EquipmentListResponse> {
  return apiFetch(`/equipment${buildQuery(params)}`);
}

export function getEquipment(id: number): Promise<Equipment> {
  return apiFetch(`/equipment/${id}`);
}

export function createEquipment(payload: EquipmentPayload): Promise<Equipment> {
  return apiFetch(`/equipment`, { method: "POST", body: JSON.stringify(payload) });
}

export function updateEquipment(id: number, payload: Partial<EquipmentPayload>): Promise<Equipment> {
  return apiFetch(`/equipment/${id}`, { method: "PUT", body: JSON.stringify(payload) });
}

export function deleteEquipment(id: number): Promise<void> {
  return apiFetch(`/equipment/${id}`, { method: "DELETE" });
}

export type EquipmentHealthFactor = {
  factor: string;
  deduction: number;
  detail: string;
};

export type EquipmentHealth = {
  equipment_id: number;
  score: number;
  band: string;
  starting_score: number;
  factors: EquipmentHealthFactor[];
  disclaimer_text: string;
  computed_at: string;
};

export function getEquipmentHealth(id: number): Promise<EquipmentHealth> {
  return apiFetch(`/equipment/${id}/health`);
}

export type EquipmentReading = {
  id: number;
  reading_at: string;
  parameter: string;
  value: number;
  unit: string | null;
};

export type EquipmentReadingListResponse = {
  items: EquipmentReading[];
  total: number;
};

export function listEquipmentReadings(
  id: number,
  params: { parameter?: string; date_from?: string; date_to?: string; page?: number; page_size?: number } = {},
): Promise<EquipmentReadingListResponse> {
  return apiFetch(`/equipment/${id}/readings${buildQuery(params)}`);
}

export function createEquipmentReading(
  id: number,
  payload: { reading_at: string; parameter: string; value: number; unit?: string | null },
): Promise<EquipmentReading> {
  return apiFetch(`/equipment/${id}/readings`, { method: "POST", body: JSON.stringify(payload) });
}

export function getEquipmentMaintenance(id: number): Promise<MaintenanceResponse> {
  return apiFetch(`/equipment/${id}/maintenance`);
}

export function getEquipmentDowntime(id: number): Promise<DowntimeResponse> {
  return apiFetch(`/equipment/${id}/downtime`);
}

export type EquipmentStatusCounts = {
  total: number;
  operating: number;
  standby: number;
  maintenance: number;
  failed: number;
  decommissioned: number;
  unknown: number;
  attention_count: number;
};

export type EquipmentHealthDistribution = {
  buckets: { band: string; count: number }[];
  unscored_count: number;
};

export type EquipmentDashboard = {
  status_counts: EquipmentStatusCounts;
  health_distribution: EquipmentHealthDistribution;
};

export function getEquipmentDashboard(): Promise<EquipmentDashboard> {
  return apiFetch(`/equipment/dashboard`);
}

export type EquipmentScopeBar = {
  key: string;
  label: string;
  count: number;
  avg_health_score: number | null;
};

export type EquipmentByScopeResponse = {
  group_by: string;
  bars: EquipmentScopeBar[];
};

export function getEquipmentByScope(params: {
  group_by?: "type" | "field" | "facility";
}): Promise<EquipmentByScopeResponse> {
  return apiFetch(`/equipment/by-scope${buildQuery(params)}`);
}

export type EquipmentInvestigationItem = {
  id: number;
  equipment_tag: string;
  name: string;
  equipment_type: string;
  status: string;
  health_score: number | null;
  health_band: string | null;
  detail: string;
};

export type EquipmentIssuesResponse = {
  items: EquipmentInvestigationItem[];
};

export function getEquipmentIssues(params: { limit?: number } = {}): Promise<EquipmentIssuesResponse> {
  return apiFetch(`/equipment/issues${buildQuery(params)}`);
}

export type ReliabilityMetrics = {
  equipment_id: number;
  mtbf_hours: number | null;
  mtbf_data_sufficient: boolean;
  mttr_hours: number | null;
  mttr_data_sufficient: boolean;
  availability_pct: number | null;
  failure_count: number;
  failure_count_annualized: number | null;
  observation_period_hours: number;
  disclaimer_text: string;
  assumptions: string[];
  computed_at: string;
};

export function getEquipmentReliability(id: number): Promise<ReliabilityMetrics> {
  return apiFetch(`/equipment/${id}/reliability`);
}

// ----- Maintenance -----

export type MaintenanceStatus =
  | "scheduled"
  | "open"
  | "in_progress"
  | "waiting_for_parts"
  | "completed"
  | "cancelled"
  | "overdue";

export type MaintenancePriority = "critical" | "high" | "medium" | "low";

// Full work-order record — named MaintenanceEntry (not MaintenanceRecord) to avoid colliding
// with the lightweight MaintenanceRecord type above, used by Wells'/Equipment's read-only
// maintenance-history sub-resource. Same naming precedent as Production's ProductionEntry.
export type MaintenanceEntry = {
  id: number;
  work_order_number: string | null;
  equipment_id: number;
  equipment_tag: string;
  equipment_name: string;
  equipment_type: string;
  field_id: number | null;
  field_name: string | null;
  facility_id: number | null;
  facility_name: string | null;
  well_id: number | null;
  well_code: string | null;
  maintenance_type: string;
  priority: MaintenancePriority;
  status: string;
  description: string | null;
  planned_start_date: string | null;
  planned_completion_date: string | null;
  start_date: string | null;
  completion_date: string | null;
  technician_id: number | null;
  technician_name: string | null;
  labor_cost: number | null;
  parts_cost: number | null;
  contractor_cost: number | null;
  other_cost: number | null;
  cost: number | null;
  downtime_hours: number | null;
  failure_cause: string | null;
  corrective_action: string | null;
  notes: string | null;
  created_at: string;
  updated_at: string;
};

export type MaintenanceListResponse = {
  items: MaintenanceEntry[];
  total: number;
  page: number;
  page_size: number;
};

export type MaintenancePayload = {
  equipment_id: number;
  maintenance_type: string;
  priority?: MaintenancePriority;
  status?: MaintenanceStatus;
  description?: string | null;
  planned_start_date?: string | null;
  planned_completion_date?: string | null;
  start_date?: string | null;
  completion_date?: string | null;
  technician_id?: number | null;
  labor_cost?: number | null;
  parts_cost?: number | null;
  contractor_cost?: number | null;
  other_cost?: number | null;
  downtime_hours?: number | null;
  failure_cause?: string | null;
  corrective_action?: string | null;
  notes?: string | null;
};

export type ListMaintenanceParams = {
  search?: string;
  equipment_id?: number;
  well_id?: number;
  field_id?: number;
  facility_id?: number;
  status?: string;
  priority?: string;
  maintenance_type?: string;
  date_from?: string;
  date_to?: string;
  sort?: string;
  order?: "asc" | "desc";
  page?: number;
  page_size?: number;
};

export function listMaintenance(params: ListMaintenanceParams = {}): Promise<MaintenanceListResponse> {
  return apiFetch(`/maintenance${buildQuery(params)}`);
}

export function getMaintenance(id: number): Promise<MaintenanceEntry> {
  return apiFetch(`/maintenance/${id}`);
}

export function createMaintenance(payload: MaintenancePayload): Promise<MaintenanceEntry> {
  return apiFetch(`/maintenance`, { method: "POST", body: JSON.stringify(payload) });
}

export function updateMaintenance(id: number, payload: Partial<MaintenancePayload>): Promise<MaintenanceEntry> {
  return apiFetch(`/maintenance/${id}`, { method: "PUT", body: JSON.stringify(payload) });
}

export function deleteMaintenance(id: number): Promise<void> {
  return apiFetch(`/maintenance/${id}`, { method: "DELETE" });
}

export type MaintenanceStatusCounts = {
  total: number;
  scheduled: number;
  open: number;
  in_progress: number;
  waiting_for_parts: number;
  completed: number;
  cancelled: number;
  overdue: number;
  emergency_count: number;
  computed_overdue_count: number;
};

export type EquipmentRequiringMaintenanceItem = {
  equipment_id: number;
  equipment_tag: string;
  equipment_name: string;
  next_maintenance_due: string;
  days_from_today: number;
};

export type MaintenanceDashboard = {
  status_counts: MaintenanceStatusCounts;
  total_cost: number;
  total_downtime_hours: number;
  equipment_requiring_maintenance: EquipmentRequiringMaintenanceItem[];
};

export function getMaintenanceDashboard(): Promise<MaintenanceDashboard> {
  return apiFetch(`/maintenance/dashboard`);
}

export type MaintenanceScopeBar = {
  key: string;
  label: string;
  count: number;
  total_cost: number;
  total_downtime_hours: number;
};

export type MaintenanceByScopeResponse = {
  group_by: string;
  bars: MaintenanceScopeBar[];
};

export function getMaintenanceByScope(params: {
  group_by?: "type" | "equipment" | "field" | "well";
}): Promise<MaintenanceByScopeResponse> {
  return apiFetch(`/maintenance/by-scope${buildQuery(params)}`);
}

export type MaintenanceCostTrendPoint = {
  month: string;
  total_cost: number;
  record_count: number;
};

export type MaintenanceCostTrendResponse = {
  points: MaintenanceCostTrendPoint[];
};

export function getMaintenanceCostTrend(): Promise<MaintenanceCostTrendResponse> {
  return apiFetch(`/maintenance/cost-trend`);
}

export type MaintenanceScheduleItem = {
  source: "work_order" | "equipment";
  id: number;
  label: string;
  equipment_id: number;
  equipment_tag: string;
  due_date: string;
  status: string | null;
  priority: string | null;
  days_from_today: number;
};

export type MaintenanceScheduleResponse = {
  reference_date: string;
  lookahead_days: number;
  overdue: MaintenanceScheduleItem[];
  due_today: MaintenanceScheduleItem[];
  upcoming: MaintenanceScheduleItem[];
};

export function getMaintenanceSchedule(): Promise<MaintenanceScheduleResponse> {
  return apiFetch(`/maintenance/schedule`);
}

// ----- Production Loss -----

export type ProductionLossCategory =
  | "equipment_failure"
  | "scheduled_maintenance"
  | "reservoir"
  | "weather"
  | "operational"
  | "market_curtailment"
  | "other";

export type ProductionLossEntry = {
  id: number;
  loss_date: string;
  category: string | null;
  cause: string | null;
  downtime_hours: number | null;
  well_id: number | null;
  well_code: string | null;
  equipment_id: number | null;
  equipment_tag: string | null;
  equipment_name: string | null;
  field_id: number | null;
  field_name: string | null;
  facility_id: number | null;
  facility_name: string | null;
  downtime_event_id: number | null;
  maintenance_record_id: number | null;
  work_order_number: string | null;
  estimated_bopd_lost: number | null;
  estimated_mscf_lost: number | null;
  estimated_revenue_impact: number | null;
  currency: string | null;
  oil_price_per_bbl: number | null;
  gas_price_per_mscf: number | null;
  disclaimer_text: string;
  created_at: string;
  updated_at: string;
};

export type ProductionLossListResponse = {
  items: ProductionLossEntry[];
  total: number;
  page: number;
  page_size: number;
};

export type ProductionLossPayload = {
  loss_date: string;
  category?: ProductionLossCategory | null;
  cause?: string | null;
  downtime_hours?: number | null;
  well_id?: number | null;
  equipment_id?: number | null;
  downtime_event_id?: number | null;
  maintenance_record_id?: number | null;
  estimated_bopd_lost?: number | null;
  estimated_mscf_lost?: number | null;
  estimated_revenue_impact?: number | null;
  currency?: string | null;
};

export type ListProductionLossParams = {
  search?: string;
  well_id?: number;
  equipment_id?: number;
  field_id?: number;
  facility_id?: number;
  category?: string;
  date_from?: string;
  date_to?: string;
  sort?: string;
  order?: "asc" | "desc";
  page?: number;
  page_size?: number;
};

export function listProductionLoss(params: ListProductionLossParams = {}): Promise<ProductionLossListResponse> {
  return apiFetch(`/production-loss${buildQuery(params)}`);
}

export function getProductionLoss(id: number): Promise<ProductionLossEntry> {
  return apiFetch(`/production-loss/${id}`);
}

export function createProductionLoss(payload: ProductionLossPayload): Promise<ProductionLossEntry> {
  return apiFetch(`/production-loss`, { method: "POST", body: JSON.stringify(payload) });
}

export function updateProductionLoss(
  id: number,
  payload: Partial<ProductionLossPayload>,
): Promise<ProductionLossEntry> {
  return apiFetch(`/production-loss/${id}`, { method: "PUT", body: JSON.stringify(payload) });
}

export function deleteProductionLoss(id: number): Promise<void> {
  return apiFetch(`/production-loss/${id}`, { method: "DELETE" });
}

export type ProductionLossCategoryCount = {
  category: string;
  count: number;
};

export type ProductionLossDashboard = {
  event_count: number;
  total_oil_bopd_lost: number;
  total_gas_mscfd_lost: number;
  total_revenue_impact: number;
  avg_downtime_hours: number;
  by_category: ProductionLossCategoryCount[];
  disclaimer_text: string;
};

export function getProductionLossDashboard(): Promise<ProductionLossDashboard> {
  return apiFetch(`/production-loss/dashboard`);
}

export type ProductionLossScopeBar = {
  key: string;
  label: string;
  count: number;
  total_oil_bopd_lost: number;
  total_gas_mscfd_lost: number;
  total_revenue_impact: number;
};

export type ProductionLossByScopeResponse = {
  group_by: string;
  bars: ProductionLossScopeBar[];
};

export function getProductionLossByScope(params: {
  group_by?: "category" | "well" | "equipment" | "field";
}): Promise<ProductionLossByScopeResponse> {
  return apiFetch(`/production-loss/by-scope${buildQuery(params)}`);
}

export type ProductionLossTrendPoint = {
  month: string;
  total_oil_bopd_lost: number;
  total_gas_mscfd_lost: number;
  total_revenue_impact: number;
  event_count: number;
};

export type ProductionLossTrendResponse = {
  points: ProductionLossTrendPoint[];
};

export function getProductionLossTrend(): Promise<ProductionLossTrendResponse> {
  return apiFetch(`/production-loss/trend`);
}

// ----- Cost & Revenue -----

export type CostCurrency = "USD" | "NGN";

export type MoneyByCurrency = {
  currency: string;
  amount: number;
};

export type OperatingCostEntry = {
  id: number;
  cost_date: string;
  category: string;
  amount: number;
  currency: string;
  description: string | null;
  cost_period: string | null;
  source: string | null;
  notes: string | null;
  field_id: number | null;
  field_name: string | null;
  facility_id: number | null;
  facility_name: string | null;
  well_id: number | null;
  well_code: string | null;
  equipment_id: number | null;
  equipment_tag: string | null;
  created_at: string;
  updated_at: string;
};

export type OperatingCostListResponse = {
  items: OperatingCostEntry[];
  total: number;
  page: number;
  page_size: number;
};

export type OperatingCostPayload = {
  cost_date: string;
  category: string;
  amount: number;
  currency?: CostCurrency;
  description?: string | null;
  cost_period?: string | null;
  source?: string | null;
  notes?: string | null;
  field_id?: number | null;
  facility_id?: number | null;
  well_id?: number | null;
  equipment_id?: number | null;
};

export type ListOperatingCostsParams = {
  search?: string;
  field_id?: number;
  facility_id?: number;
  well_id?: number;
  equipment_id?: number;
  category?: string;
  currency?: string;
  date_from?: string;
  date_to?: string;
  sort?: string;
  order?: "asc" | "desc";
  page?: number;
  page_size?: number;
};

export function listOperatingCosts(params: ListOperatingCostsParams = {}): Promise<OperatingCostListResponse> {
  return apiFetch(`/operating-costs${buildQuery(params)}`);
}

export function getOperatingCost(id: number): Promise<OperatingCostEntry> {
  return apiFetch(`/operating-costs/${id}`);
}

export function createOperatingCost(payload: OperatingCostPayload): Promise<OperatingCostEntry> {
  return apiFetch(`/operating-costs`, { method: "POST", body: JSON.stringify(payload) });
}

export function updateOperatingCost(id: number, payload: Partial<OperatingCostPayload>): Promise<OperatingCostEntry> {
  return apiFetch(`/operating-costs/${id}`, { method: "PUT", body: JSON.stringify(payload) });
}

export function deleteOperatingCost(id: number): Promise<void> {
  return apiFetch(`/operating-costs/${id}`, { method: "DELETE" });
}

export type ProductionTotals = {
  oil_bbl: number;
  gas_mscf: number;
  boe: number;
};

export type RevenueSection = {
  oil: MoneyByCurrency[];
  gas: MoneyByCurrency[];
  total: MoneyByCurrency[];
};

export type CostSection = {
  operating: MoneyByCurrency[];
  maintenance: MoneyByCurrency[];
  energy: MoneyByCurrency[];
  other: MoneyByCurrency[];
  total: MoneyByCurrency[];
};

export type EconomicsSection = {
  margin: MoneyByCurrency[];
  cost_per_bbl: MoneyByCurrency[];
  cost_per_boe: MoneyByCurrency[];
  revenue_per_bbl: MoneyByCurrency[];
  revenue_per_boe: MoneyByCurrency[];
  currency_mismatch: boolean;
};

export type ProductionLossEconomicsSection = {
  estimated_lost_oil_bbl: number;
  estimated_lost_gas_mscf: number;
  estimated_lost_revenue: MoneyByCurrency[];
  downtime_hours: number;
};

export type CostRevenueDashboard = {
  period_start: string;
  period_end: string;
  production: ProductionTotals;
  revenue: RevenueSection;
  costs: CostSection;
  economics: EconomicsSection;
  production_loss: ProductionLossEconomicsSection;
  disclaimer_text: string;
};

export function getCostRevenueDashboard(): Promise<CostRevenueDashboard> {
  return apiFetch(`/cost-revenue/dashboard`);
}

export type UnitEconomics = {
  period_start: string;
  period_end: string;
  production: ProductionTotals;
  revenue: RevenueSection;
  costs: CostSection;
  economics: EconomicsSection;
  disclaimer_text: string;
};

export function getUnitEconomics(params: {
  field_id?: number;
  facility_id?: number;
  well_id?: number;
  date_from?: string;
  date_to?: string;
} = {}): Promise<UnitEconomics> {
  return apiFetch(`/cost-revenue/unit-economics${buildQuery(params)}`);
}

export type EconomicsScopeRow = {
  scope: "field" | "well";
  key: string;
  label: string;
  oil_bbl: number;
  gas_mscf: number;
  boe: number;
  revenue: MoneyByCurrency[];
  operating_cost: MoneyByCurrency[];
  maintenance_cost: number;
  production_loss_revenue: MoneyByCurrency[];
  margin: MoneyByCurrency[];
  cost_per_bbl: MoneyByCurrency[];
  revenue_per_bbl: MoneyByCurrency[];
  currency_mismatch: boolean;
  high_production: boolean | null;
  high_cost: boolean | null;
  low_margin: boolean | null;
  high_loss: boolean | null;
  review_note: string | null;
};

export type EconomicsByScopeResponse = {
  scope: string;
  rank_by: string;
  rows: EconomicsScopeRow[];
  disclaimer_text: string;
};

export function getEconomicsByScope(params: {
  scope: "field" | "well";
  rank_by?: "production" | "revenue" | "cost_efficiency" | "margin";
}): Promise<EconomicsByScopeResponse> {
  return apiFetch(`/cost-revenue/economics-by-scope${buildQuery(params)}`);
}

export type RevenueTrendPoint = {
  month: string;
  oil_revenue: MoneyByCurrency[];
  gas_revenue: MoneyByCurrency[];
  total_revenue: MoneyByCurrency[];
  revenue_per_bbl: MoneyByCurrency[];
};

export type RevenueTrendResponse = {
  points: RevenueTrendPoint[];
};

export function getRevenueTrend(params: {
  field_id?: number;
  facility_id?: number;
  well_id?: number;
  commodity?: "oil" | "gas";
} = {}): Promise<RevenueTrendResponse> {
  return apiFetch(`/cost-revenue/revenue-trend${buildQuery(params)}`);
}

export type CostTrendPoint = {
  month: string;
  total_cost: MoneyByCurrency[];
  cost_per_bbl: MoneyByCurrency[];
};

export type CostTrendResponse = {
  points: CostTrendPoint[];
};

export function getOperatingCostTrend(params: {
  field_id?: number;
  facility_id?: number;
  well_id?: number;
  category?: string;
} = {}): Promise<CostTrendResponse> {
  return apiFetch(`/cost-revenue/cost-trend${buildQuery(params)}`);
}

export type MarginTrendPoint = {
  month: string;
  margin: MoneyByCurrency[];
};

export type MarginTrendResponse = {
  points: MarginTrendPoint[];
};

export function getMarginTrend(params: {
  field_id?: number;
  facility_id?: number;
  well_id?: number;
} = {}): Promise<MarginTrendResponse> {
  return apiFetch(`/cost-revenue/margin-trend${buildQuery(params)}`);
}

export type CostAlert = {
  severity: "info" | "warning" | "critical";
  category: string;
  scope_label: string;
  message: string;
  detail: string;
};

export type CostAlertsResponse = {
  alerts: CostAlert[];
  disclaimer_text: string;
};

export function getCostAlerts(): Promise<CostAlertsResponse> {
  return apiFetch(`/cost-revenue/alerts`);
}

// ----- Alerts (centralized Alert & Event Intelligence) -----

export type AlertSeverity = "critical" | "high" | "medium" | "low" | "informational";
export type AlertCategory = "production" | "equipment" | "maintenance" | "production_loss" | "economics";
export type AlertStatus = "new" | "acknowledged" | "investigating" | "resolved" | "dismissed";

export type AlertEntry = {
  id: number;
  alert_type: string;
  category: string;
  source_module: string;
  severity: string;
  status: string;
  title: string;
  description: string;
  recommended_action: string | null;
  notes: string | null;
  well_id: number | null;
  well_code: string | null;
  field_id: number | null;
  field_name: string | null;
  facility_id: number | null;
  facility_name: string | null;
  equipment_id: number | null;
  equipment_tag: string | null;
  maintenance_record_id: number | null;
  maintenance_work_order_number: string | null;
  production_loss_id: number | null;
  threshold_value: number | null;
  current_value: number | null;
  unit: string | null;
  dedup_key: string;
  occurrence_count: number;
  triggered_at: string;
  last_detected_at: string;
  acknowledged_at: string | null;
  resolved_at: string | null;
  acknowledged_by_name: string | null;
  resolved_by_name: string | null;
  created_at: string;
  updated_at: string;
  disclaimer_text: string;
};

export type AlertListResponse = {
  items: AlertEntry[];
  total: number;
  page: number;
  page_size: number;
};

export type ListAlertsParams = {
  search?: string;
  severity?: string;
  category?: string;
  status?: string;
  field_id?: number;
  facility_id?: number;
  well_id?: number;
  equipment_id?: number;
  date_from?: string;
  date_to?: string;
  sort?: string;
  order?: "asc" | "desc";
  page?: number;
  page_size?: number;
};

export function listAlerts(params: ListAlertsParams = {}): Promise<AlertListResponse> {
  return apiFetch(`/alerts${buildQuery(params)}`);
}

export function getAlert(id: number): Promise<AlertEntry> {
  return apiFetch(`/alerts/${id}`);
}

export type AlertCreatePayload = {
  category: AlertCategory;
  alert_type: string;
  severity: AlertSeverity;
  title: string;
  description: string;
  recommended_action?: string | null;
  notes?: string | null;
  well_id?: number | null;
  field_id?: number | null;
  facility_id?: number | null;
  equipment_id?: number | null;
  maintenance_record_id?: number | null;
  production_loss_id?: number | null;
  threshold_value?: number | null;
  current_value?: number | null;
  unit?: string | null;
};

export function createAlert(payload: AlertCreatePayload): Promise<AlertEntry> {
  return apiFetch(`/alerts`, { method: "POST", body: JSON.stringify(payload) });
}

export type AlertUpdatePayload = {
  title?: string;
  description?: string;
  severity?: AlertSeverity;
  recommended_action?: string | null;
  notes?: string | null;
};

export function updateAlert(id: number, payload: AlertUpdatePayload): Promise<AlertEntry> {
  return apiFetch(`/alerts/${id}`, { method: "PUT", body: JSON.stringify(payload) });
}

function alertStatusChange(id: number, action: string, note?: string): Promise<AlertEntry> {
  return apiFetch(`/alerts/${id}/${action}`, { method: "PUT", body: JSON.stringify({ note: note ?? null }) });
}

export function acknowledgeAlert(id: number, note?: string): Promise<AlertEntry> {
  return alertStatusChange(id, "acknowledge", note);
}

export function investigateAlert(id: number, note?: string): Promise<AlertEntry> {
  return alertStatusChange(id, "investigate", note);
}

export function resolveAlert(id: number, note?: string): Promise<AlertEntry> {
  return alertStatusChange(id, "resolve", note);
}

export function dismissAlert(id: number, note?: string): Promise<AlertEntry> {
  return alertStatusChange(id, "dismiss", note);
}

export function addAlertNote(id: number, note: string): Promise<AlertEntry> {
  return apiFetch(`/alerts/${id}/notes`, { method: "POST", body: JSON.stringify({ note }) });
}

export type AlertHistoryEntry = {
  id: number;
  from_state: string | null;
  to_state: string;
  note: string | null;
  changed_by_name: string | null;
  changed_at: string;
};

export type AlertHistoryResponse = {
  items: AlertHistoryEntry[];
};

export function getAlertHistory(id: number): Promise<AlertHistoryResponse> {
  return apiFetch(`/alerts/${id}/history`);
}

export type SeverityCounts = {
  critical: number;
  high: number;
  medium: number;
  low: number;
  informational: number;
};

export type StatusCounts = {
  new: number;
  acknowledged: number;
  investigating: number;
  resolved: number;
  dismissed: number;
};

export type CategoryCount = { category: string; count: number };
export type ScopeCount = { key: string; label: string; count: number };

export type AlertSummaryResponse = {
  total: number;
  open_count: number;
  by_severity: SeverityCounts;
  by_status: StatusCounts;
  by_category: CategoryCount[];
  by_field: ScopeCount[];
  by_equipment: ScopeCount[];
  recent: AlertEntry[];
  disclaimer_text: string;
};

export function getAlertSummary(): Promise<AlertSummaryResponse> {
  return apiFetch(`/alerts/summary`);
}

export type AlertRunCategoryResult = { created: number; updated: number };

export type AlertRunResponse = {
  created: number;
  updated: number;
  auto_resolved: number;
  by_category: Record<string, AlertRunCategoryResult>;
  disclaimer_text: string;
};

export function runAlertRules(): Promise<AlertRunResponse> {
  return apiFetch(`/alerts/run`, { method: "POST" });
}

// ----- AI Insights -----

export type InsightCategory = "production" | "equipment" | "maintenance" | "production_loss" | "economics" | "cross_domain" | "optimization";
export type InsightStatus = "new" | "reviewed" | "dismissed";
export type ConfidenceLevel = "high" | "medium" | "low";
export type EvidenceType = "observed_fact" | "calculated_metric" | "correlation" | "possible_contributor";
export type FeedbackType = "useful" | "not_useful" | "incorrect" | "needs_review";

export type InsightEvidence = {
  id: number;
  evidence_type: EvidenceType;
  description: string;
  source_type: string | null;
  source_id: number | null;
  source_label: string | null;
  value: number | null;
  unit: string | null;
};

export type InsightFeedbackEntry = {
  id: number;
  feedback: FeedbackType;
  notes: string | null;
  submitted_by_name: string | null;
  submitted_at: string;
};

export type InsightEntry = {
  id: number;
  insight_type: string;
  category: InsightCategory;
  severity: string;
  status: InsightStatus;
  generated_by: string;
  ai_provider: string | null;
  ai_model: string | null;
  ai_interpretation: string | null;

  title: string;
  summary: string;
  recommended_investigation: string | null;
  data_quality_note: string | null;
  confidence_level: ConfidenceLevel;

  estimated_production_impact_value: number | null;
  estimated_production_impact_unit: string | null;
  estimated_production_impact_note: string | null;
  estimated_financial_impact_value: number | null;
  estimated_financial_impact_currency: string | null;
  estimated_financial_impact_note: string | null;

  well_id: number | null;
  well_code: string | null;
  field_id: number | null;
  field_name: string | null;
  facility_id: number | null;
  facility_name: string | null;
  equipment_id: number | null;
  equipment_tag: string | null;
  maintenance_record_id: number | null;
  maintenance_work_order_number: string | null;
  production_loss_id: number | null;
  alert_id: number | null;

  dedup_key: string;
  occurrence_count: number;

  generated_at: string;
  last_confirmed_at: string;
  is_stale: boolean;
  days_since_confirmed: number;

  created_at: string;
  updated_at: string;

  disclaimer_text: string;
  evidence: InsightEvidence[];
  feedback: InsightFeedbackEntry[];
};

export type InsightListResponse = {
  items: InsightEntry[];
  total: number;
  page: number;
  page_size: number;
};

export type ListInsightsParams = {
  search?: string;
  category?: string;
  insight_type?: string;
  severity?: string;
  confidence_level?: string;
  status?: string;
  field_id?: number;
  facility_id?: number;
  well_id?: number;
  equipment_id?: number;
  date_from?: string;
  date_to?: string;
  sort?: string;
  order?: "asc" | "desc";
  page?: number;
  page_size?: number;
};

export function listInsights(params: ListInsightsParams = {}): Promise<InsightListResponse> {
  return apiFetch(`/ai-insights${buildQuery(params)}`);
}

export function getInsight(id: number): Promise<InsightEntry> {
  return apiFetch(`/ai-insights/${id}`);
}

export function updateInsightStatus(id: number, status: "reviewed" | "dismissed"): Promise<InsightEntry> {
  return apiFetch(`/ai-insights/${id}/status`, { method: "PUT", body: JSON.stringify({ status }) });
}

export function submitInsightFeedback(
  id: number,
  payload: { feedback: FeedbackType; notes?: string | null }
): Promise<InsightEntry> {
  return apiFetch(`/ai-insights/${id}/feedback`, { method: "POST", body: JSON.stringify(payload) });
}

export type InterpretResponse = {
  insight_id: number;
  interpretation: string;
  provider: string;
  model: string | null;
  disclaimer_text: string;
};

export function interpretInsight(id: number): Promise<InterpretResponse> {
  return apiFetch(`/ai-insights/${id}/interpret`, { method: "POST" });
}

export type InsightRunCategoryResult = { created: number; updated: number };

export type InsightRunResponse = {
  created: number;
  updated: number;
  by_category: Record<string, InsightRunCategoryResult>;
  disclaimer_text: string;
};

export function runInsightEngine(): Promise<InsightRunResponse> {
  return apiFetch(`/ai-insights/run`, { method: "POST" });
}

export type SourceReference = { source_type: string; source_id: number | null; source_label: string };

export type AssistantAnswer = {
  answer: string;
  sources: SourceReference[];
  answered_by: "deterministic" | "ai";
  disclaimer_text: string;
};

export function askAssistant(question: string): Promise<AssistantAnswer> {
  return apiFetch(`/ai-insights/assistant`, { method: "POST", body: JSON.stringify({ question }) });
}

export type PossibleCause = {
  description: string;
  evidence_type: "observed_fact" | "calculated_metric" | "correlation" | "possible_contributor";
};

export type InvestigationResult = {
  event: string;
  impact_summary: string;
  primary_contributor: string | null;
  possible_causes: PossibleCause[];
  ai_assessment: string;
  confidence_level: "high" | "medium" | "low";
  recommended_investigation: string;
  sources: SourceReference[];
  answered_by: "deterministic" | "ai";
  disclaimer_text: string;
};

export type InvestigateTarget = { insight_id?: number; well_id?: number; equipment_id?: number };

export function investigateEvent(target: InvestigateTarget): Promise<InvestigationResult> {
  return apiFetch(`/ai-insights/investigate`, { method: "POST", body: JSON.stringify(target) });
}

export type InsightSeverityCounts = {
  critical: number;
  high: number;
  medium: number;
  low: number;
  informational: number;
};

export type InsightCategoryCount = { category: string; count: number };

export type InsightSummary = {
  total: number;
  open_count: number;
  by_severity: InsightSeverityCounts;
  by_category: InsightCategoryCount[];
  by_confidence: Record<string, number>;
  recent: InsightEntry[];
  critical: InsightEntry[];
  disclaimer_text: string;
};

export function getInsightSummary(): Promise<InsightSummary> {
  return apiFetch(`/ai-insights/summary`);
}

export type DailyBriefSection = { title: string; summary: string; items: string[] };

export type DailyBrief = {
  generated_at: string;
  period_label: string;
  sections: DailyBriefSection[];
  narrative: string | null;
  disclaimer_text: string;
};

export function getDailyBrief(narrative = false): Promise<DailyBrief> {
  return apiFetch(`/ai-insights/daily-brief${buildQuery({ narrative: narrative ? "true" : undefined })}`);
}

export type ManagementSummarySection = { question: string; answer: string };

export type ManagementSummary = {
  generated_at: string;
  period_label: string;
  sections: ManagementSummarySection[];
  narrative: string | null;
  disclaimer_text: string;
};

export function getManagementSummary(narrative = false): Promise<ManagementSummary> {
  return apiFetch(`/ai-insights/management-summary${buildQuery({ narrative: narrative ? "true" : undefined })}`);
}

// ----- What-If Simulator -----
// Mirrors backend/app/schemas/whatif.py field-for-field. Every scenario is a planning artifact
// only — creating/running one never touches production/cost/maintenance records.

export type BaselineConfig = {
  date_from: string;
  date_to: string;
  field_id?: number | null;
  facility_id?: number | null;
  well_id?: number | null;
  equipment_id?: number | null;
};

export type ScenarioAssumptions = {
  production_change_pct?: number | null;
  downtime_change_pct?: number | null;
  production_loss_reduction_pct?: number | null;
  operating_cost_change_pct?: number | null;
  energy_cost_change_pct?: number | null;
  maintenance_cost_change_pct?: number | null;
  oil_price_override?: number | null;
  oil_price_change_pct?: number | null;
  gas_price_override?: number | null;
  gas_price_change_pct?: number | null;
};

export const SCENARIO_ASSUMPTION_FIELDS: (keyof ScenarioAssumptions)[] = [
  "production_change_pct",
  "downtime_change_pct",
  "production_loss_reduction_pct",
  "operating_cost_change_pct",
  "energy_cost_change_pct",
  "maintenance_cost_change_pct",
  "oil_price_override",
  "oil_price_change_pct",
  "gas_price_override",
  "gas_price_change_pct",
];

export type GuardrailFlag = {
  field: string;
  message: string;
  severity: "error" | "warning";
};

export type BaselineMetrics = {
  period_start: string;
  period_end: string;
  period_days: number;
  oil_bbl: number;
  gas_mscf: number;
  boe: number;
  oil_price: number | null;
  oil_price_currency: string | null;
  gas_price: number | null;
  gas_price_currency: string | null;
  revenue: MoneyByCurrency[];
  operating_cost: MoneyByCurrency[];
  maintenance_cost: MoneyByCurrency[];
  total_cost: MoneyByCurrency[];
  lost_oil_bbl: number;
  lost_gas_mscf: number;
  production_loss_revenue: MoneyByCurrency[];
  downtime_hours: number;
  margin: MoneyByCurrency[];
  margin_currency_mismatch: boolean;
  data_sufficient: boolean;
  missing_data_note: string | null;
};

export type ScenarioMetrics = {
  oil_bbl: number;
  gas_mscf: number;
  boe: number;
  oil_price: number | null;
  oil_price_currency: string | null;
  gas_price: number | null;
  gas_price_currency: string | null;
  revenue: MoneyByCurrency[];
  operating_cost: MoneyByCurrency[];
  maintenance_cost: MoneyByCurrency[];
  total_cost: MoneyByCurrency[];
  lost_oil_bbl: number;
  lost_gas_mscf: number;
  production_loss_revenue: MoneyByCurrency[];
  downtime_hours: number;
  margin: MoneyByCurrency[];
  margin_currency_mismatch: boolean;
  recovered_downtime_hours: number;
  recovered_production_bbl: number;
  potential_loss_reduction_oil_bbl: number;
  potential_loss_reduction_gas_mscf: number;
  potential_loss_reduction_revenue: MoneyByCurrency[];
  potential_cost_saving: MoneyByCurrency[];
};

export type ComparisonRow = {
  metric: string;
  baseline: number;
  scenario: number;
  difference: number;
  pct_change: number | null;
  currency: string | null;
  direction: "positive" | "negative" | "neutral";
};

export type ScenarioResults = {
  baseline: BaselineMetrics;
  scenario: ScenarioMetrics;
  comparison: ComparisonRow[];
  guardrail_flags: GuardrailFlag[];
};

export type ScenarioListItem = {
  id: number;
  name: string;
  description: string | null;
  created_by_id: number;
  created_by_name: string | null;
  baseline_date_from: string;
  baseline_date_to: string;
  field_id: number | null;
  field_name: string | null;
  facility_id: number | null;
  facility_name: string | null;
  well_id: number | null;
  well_code: string | null;
  equipment_id: number | null;
  equipment_tag: string | null;
  calculation_version: string;
  last_run_at: string | null;
  created_at: string;
  updated_at: string;
  has_results: boolean;
};

export type Scenario = ScenarioListItem & {
  assumptions: ScenarioAssumptions;
  results: ScenarioResults | null;
  disclaimer_text: string;
};

export type ScenarioListResponse = {
  items: ScenarioListItem[];
  total: number;
  page: number;
  page_size: number;
};

export type ListScenariosParams = {
  search?: string;
  created_by_id?: number;
  field_id?: number;
  well_id?: number;
  sort?: string;
  order?: "asc" | "desc";
  page?: number;
  page_size?: number;
};

export function listScenarios(params: ListScenariosParams = {}): Promise<ScenarioListResponse> {
  return apiFetch(`/what-if/scenarios${buildQuery(params)}`);
}

export function getScenario(id: number): Promise<Scenario> {
  return apiFetch(`/what-if/scenarios/${id}`);
}

export type ScenarioCreatePayload = {
  name: string;
  description?: string | null;
  baseline: BaselineConfig;
  assumptions: ScenarioAssumptions;
};

export function createScenario(payload: ScenarioCreatePayload): Promise<Scenario> {
  return apiFetch(`/what-if/scenarios`, { method: "POST", body: JSON.stringify(payload) });
}

export type ScenarioUpdatePayload = {
  name?: string;
  description?: string | null;
  baseline?: BaselineConfig;
  assumptions?: ScenarioAssumptions;
};

export function updateScenario(id: number, payload: ScenarioUpdatePayload): Promise<Scenario> {
  return apiFetch(`/what-if/scenarios/${id}`, { method: "PUT", body: JSON.stringify(payload) });
}

export function deleteScenario(id: number): Promise<void> {
  return apiFetch(`/what-if/scenarios/${id}`, { method: "DELETE" });
}

export function rerunScenario(id: number): Promise<Scenario> {
  return apiFetch(`/what-if/scenarios/${id}/rerun`, { method: "POST" });
}

export type PreviewResponse = {
  results: ScenarioResults;
  calculation_version: string;
  disclaimer_text: string;
};

export function previewScenario(baseline: BaselineConfig, assumptions: ScenarioAssumptions): Promise<PreviewResponse> {
  return apiFetch(`/what-if/preview`, { method: "POST", body: JSON.stringify({ baseline, assumptions }) });
}

export type ScenarioCompareEntry = {
  id: number;
  name: string;
  results: ScenarioResults | null;
};

export type CompareResponse = {
  scenarios: ScenarioCompareEntry[];
  ai_narrative: string | null;
  disclaimer_text: string;
};

export function compareScenarios(scenarioIds: number[], narrative = false): Promise<CompareResponse> {
  return apiFetch(`/what-if/compare`, {
    method: "POST",
    body: JSON.stringify({ scenario_ids: scenarioIds, narrative }),
  });
}

export type SensitivityPoint = {
  variable_value: number;
  recovered_production_bbl: number;
  recovered_downtime_hours: number;
  revenue_impact: MoneyByCurrency[];
  margin_impact: MoneyByCurrency[];
};

export type SensitivityResponse = {
  baseline: BaselineMetrics;
  variable: string;
  points: SensitivityPoint[];
  disclaimer_text: string;
};

export function runSensitivity(
  baseline: BaselineConfig,
  baseAssumptions: ScenarioAssumptions,
  variable: keyof ScenarioAssumptions,
  values: number[]
): Promise<SensitivityResponse> {
  return apiFetch(`/what-if/sensitivity`, {
    method: "POST",
    body: JSON.stringify({ baseline, base_assumptions: baseAssumptions, variable, values }),
  });
}

export type ScenarioInterpretResponse = {
  scenario_id: number;
  interpretation: string;
  provider: string;
  model: string | null;
  disclaimer_text: string;
};

export function interpretScenario(id: number): Promise<ScenarioInterpretResponse> {
  return apiFetch(`/what-if/scenarios/${id}/interpret`, { method: "POST" });
}

// ----- Reports -----
// Mirrors backend/app/schemas/reports.py + services/report_calculations.py. `results.sections`
// is intentionally a loosely-typed dict on the backend (4 report types, structurally different
// section sets) — these TS interfaces describe exactly what report_calculations.py actually
// produces per section, matching the "typed on the frontend, not backend-pydantic-enforced" design.

export type ReportType = "daily_operations" | "weekly_production" | "monthly_management" | "what_if_scenario";

export type ReportFilters = {
  date_from?: string | null;
  date_to?: string | null;
  field_id?: number | null;
  facility_id?: number | null;
  well_id?: number | null;
  equipment_id?: number | null;
  commodity?: string | null;
  maintenance_type?: string | null;
  alert_severity?: string | null;
  production_loss_category?: string | null;
  // What-If Scenario Report only — selects the one saved Scenario to embed.
  scenario_id?: number | null;
};

export type ReportTypeInfo = {
  id: ReportType;
  label: string;
  sections: string[];
};

export type ReportTypesResponse = {
  types: ReportTypeInfo[];
};

export function getReportTypes(): Promise<ReportTypesResponse> {
  return apiFetch(`/reports/types`);
}

export type ReportSectionTraceability = {
  source_module: string;
  methodology: string;
  record_count: number | null;
};

export type ReportProductionSection = {
  kpis: ProductionKpis;
  _traceability: ReportSectionTraceability;
};

export type ReportEquipmentSection = {
  total_equipment: number;
  health_band_counts: Record<string, number>;
  critical_equipment: { id: number; equipment_tag: string; name: string | null; status: string; health_score: number | null }[];
  _traceability: ReportSectionTraceability;
};

export type ReportMaintenanceSection = {
  record_count: number;
  total_cost: number;
  total_downtime_hours: number;
  by_type: Record<string, number>;
  preventive_count: number;
  corrective_count: number;
  emergency_count: number;
  overdue: Record<string, unknown>[];
  due_today: Record<string, unknown>[];
  _traceability: ReportSectionTraceability;
};

export type ReportLossEvent = {
  id: number;
  loss_date: string;
  well_code: string | null;
  equipment_tag: string | null;
  category: string | null;
  cause: string | null;
  estimated_revenue_impact: number | null;
  currency: string | null;
};

export type ReportProductionLossSection = {
  event_count: number;
  total_oil_bopd_lost: number;
  total_gas_mscfd_lost: number;
  total_downtime_hours: number;
  estimated_revenue_impact: MoneyByCurrency[];
  top_loss_events: ReportLossEvent[];
  top_affected_wells: { well_code: string; estimated_revenue_impact: number }[];
  top_affected_equipment: { equipment_tag: string; estimated_revenue_impact: number }[];
  _traceability: ReportSectionTraceability;
};

export type ReportEconomicsSection = {
  data_sufficient?: boolean;
  missing_data_note?: string;
  oil_bbl?: number;
  gas_mscf?: number;
  boe?: number;
  estimated_revenue?: MoneyByCurrency[];
  operating_cost?: MoneyByCurrency[];
  maintenance_cost_usd?: number;
  cost_per_bbl?: MoneyByCurrency[];
  cost_per_boe?: MoneyByCurrency[];
  estimated_operating_margin?: MoneyByCurrency[];
  margin_currency_mismatch?: boolean;
  _traceability?: ReportSectionTraceability;
};

export type ReportAlertsSection = {
  total: number;
  critical_count: number;
  high_count: number;
  open_count: number;
  resolved_count: number;
  by_severity: Record<string, number>;
  by_status: Record<string, number>;
  recent: AlertEntry[];
  _traceability: ReportSectionTraceability;
};

export type ReportInsightSummary = {
  id: number;
  title: string;
  summary: string;
  severity: string;
  confidence_level: string;
  category: string;
  estimated_production_impact_value: number | null;
  estimated_production_impact_unit: string | null;
  estimated_financial_impact_value: number | null;
  estimated_financial_impact_currency: string | null;
  recommended_investigation: string | null;
  evidence: InsightEvidence[];
};

export type ReportAiInsightsSection = {
  total: number;
  highest_priority: ReportInsightSummary[];
  _traceability: ReportSectionTraceability;
};

export type ReportProductionTrendSection = {
  points: Record<string, number | string | null>[];
  _traceability: ReportSectionTraceability;
};

export type ReportScopeBar = { key: string; label: string; oil_bopd: number; gas_mscfd: number; water_bwpd: number; boe: number };

export type ReportProductionByScopeSection = {
  by_field: ReportScopeBar[];
  by_facility: ReportScopeBar[];
  top_wells: ReportScopeBar[];
  lowest_wells: ReportScopeBar[];
  _traceability: ReportSectionTraceability;
};

export type ReportActualVsTargetSection = {
  points: { record_date: string; actual_oil_bopd: number; target_oil_bopd: number | null }[];
  _traceability: ReportSectionTraceability;
};

export type ReportExecutiveSummarySection = {
  what_happened: string;
  why_it_matters: string;
  biggest_risks: string[];
  biggest_opportunities: string[];
  recommended_investigations: string[];
};

export type ReportWhatIfScenarioSection = {
  scenario_id: number;
  scenario_name: string;
  assumptions: ScenarioAssumptions;
  results: ScenarioResults | null;
  label: "Scenario Estimate";
  _traceability: ReportSectionTraceability;
};

export type ReportSections = {
  production?: ReportProductionSection;
  equipment?: ReportEquipmentSection;
  maintenance?: ReportMaintenanceSection;
  production_loss?: ReportProductionLossSection;
  economics?: ReportEconomicsSection;
  alerts?: ReportAlertsSection;
  ai_insights?: ReportAiInsightsSection;
  production_trend?: ReportProductionTrendSection;
  production_by_scope?: ReportProductionByScopeSection;
  actual_vs_target?: ReportActualVsTargetSection;
  executive_summary?: ReportExecutiveSummarySection;
  scenario?: ReportWhatIfScenarioSection;
};

export type ReportResults = {
  report_type: ReportType;
  generated_at: string;
  filters: ReportFilters;
  sections: ReportSections;
  disclaimer_text: string;
  synthetic_data_disclaimer: string;
  ai_narrative?: string | null;
  ai_narrative_provider?: string | null;
  // Only present on a what_if_scenario report when no scenario_id was selected.
  data_sufficient?: boolean;
  missing_data_note?: string;
};

export type ReportListItem = {
  id: number;
  report_type: ReportType;
  name: string;
  description: string | null;
  created_by_id: number;
  created_by_name: string | null;
  period_start: string | null;
  period_end: string | null;
  calculation_version: string;
  status: string;
  last_generated_at: string | null;
  created_at: string;
  updated_at: string;
  has_results: boolean;
};

export type Report = ReportListItem & {
  filters: ReportFilters;
  sections: string[];
  results: ReportResults | null;
  disclaimer_text: string;
};

export type ReportListResponse = {
  items: ReportListItem[];
  total: number;
  page: number;
  page_size: number;
};

export type ListReportsParams = {
  search?: string;
  report_type?: string;
  created_by_id?: number;
  sort?: string;
  order?: "asc" | "desc";
  page?: number;
  page_size?: number;
};

export function listReports(params: ListReportsParams = {}): Promise<ReportListResponse> {
  return apiFetch(`/reports${buildQuery(params)}`);
}

export function getReport(id: number): Promise<Report> {
  return apiFetch(`/reports/${id}`);
}

export type ReportCreatePayload = {
  report_type: ReportType;
  name: string;
  description?: string | null;
  filters: ReportFilters;
  sections?: string[] | null;
  narrative?: boolean;
};

export function createReport(payload: ReportCreatePayload): Promise<Report> {
  return apiFetch(`/reports`, { method: "POST", body: JSON.stringify(payload) });
}

export type ReportUpdatePayload = {
  name?: string;
  description?: string | null;
  filters?: ReportFilters;
  sections?: string[];
};

export function updateReport(id: number, payload: ReportUpdatePayload): Promise<Report> {
  return apiFetch(`/reports/${id}`, { method: "PUT", body: JSON.stringify(payload) });
}

export function deleteReport(id: number): Promise<void> {
  return apiFetch(`/reports/${id}`, { method: "DELETE" });
}

export function regenerateReport(id: number): Promise<Report> {
  return apiFetch(`/reports/${id}/regenerate`, { method: "POST" });
}

export type PreviewReportPayload = {
  report_type: ReportType;
  filters: ReportFilters;
  sections?: string[] | null;
  narrative?: boolean;
};

export type PreviewReportResponse = {
  report_type: ReportType;
  calculation_version: string;
  results: ReportResults;
};

export function previewReport(payload: PreviewReportPayload): Promise<PreviewReportResponse> {
  return apiFetch(`/reports/preview`, { method: "POST", body: JSON.stringify(payload) });
}

/** Streams a saved report's export (CSV or PDF) and triggers a browser download — mirrors
 * `exportProductionCsv`'s manual fetch+blob+synthetic-<a>-click pattern exactly, since binary
 * downloads bypass `apiFetch`'s always-`response.json()` assumption. */
export async function exportReport(id: number, format: "csv" | "pdf", filename?: string): Promise<void> {
  if (typeof window === "undefined") return;
  const token = getToken();
  const headers = new Headers();
  if (token) headers.set("Authorization", `Bearer ${token}`);

  const response = await fetch(`${API_URL}/reports/${id}/export${buildQuery({ format })}`, { headers });
  if (!response.ok) {
    throw new ApiError(response.status, "Export failed");
  }
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename ?? `report.${format}`;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}

// ----- Administration -----
// Mirrors backend/app/schemas/{user,administration}.py. Administration is Administrator-only
// end to end (including reads) — see services/permissions.py's docstring on the backend for why
// this module departs from every other module's "reads open to all roles" pattern.

export type User = {
  id: number;
  email: string;
  full_name: string;
  is_active: boolean;
  role_id: number;
  role_name: string;
  created_at: string;
  updated_at: string;
};

export type UserListResponse = {
  items: User[];
  total: number;
  page: number;
  page_size: number;
};

export type UserCreatePayload = {
  email: string;
  full_name: string;
  password: string;
  role_id: number;
  is_active?: boolean;
};

export type UserUpdatePayload = {
  full_name?: string;
  role_id?: number;
  is_active?: boolean;
};

export function getUser(id: number): Promise<User> {
  return apiFetch(`/users/${id}`);
}

export function createUser(payload: UserCreatePayload): Promise<User> {
  return apiFetch(`/users`, { method: "POST", body: JSON.stringify(payload) });
}

export function updateUser(id: number, payload: UserUpdatePayload): Promise<User> {
  return apiFetch(`/users/${id}`, { method: "PUT", body: JSON.stringify(payload) });
}

export type ListAdministrationUsersParams = {
  search?: string;
  role_id?: number;
  is_active?: boolean;
  page?: number;
  page_size?: number;
};

export function listAdministrationUsers(params: ListAdministrationUsersParams = {}): Promise<UserListResponse> {
  const { is_active, ...rest } = params;
  return apiFetch(
    `/administration/users${buildQuery({ ...rest, is_active: is_active === undefined ? undefined : String(is_active) })}`
  );
}

export type Role = {
  id: number;
  name: string;
  description: string | null;
  user_count: number;
};

export function listRoles(): Promise<Role[]> {
  return apiFetch(`/administration/roles`);
}

export type PermissionMatrixEntry = {
  module: string;
  action: string;
  roles: string[];
  note: string | null;
};

export function getPermissions(): Promise<PermissionMatrixEntry[]> {
  return apiFetch(`/administration/permissions`);
}

export type AuditLogEntry = {
  id: number;
  action: string;
  entity_type: string | null;
  entity_id: number | null;
  details: string | null;
  status: string;
  metadata_json: Record<string, unknown> | null;
  user_id: number | null;
  user_email: string | null;
  created_at: string;
};

export type AuditLogListResponse = {
  items: AuditLogEntry[];
  total: number;
  page: number;
  page_size: number;
};

export type ListAuditLogParams = {
  search?: string;
  user_id?: number;
  action?: string;
  resource?: string;
  date_from?: string;
  date_to?: string;
  page?: number;
  page_size?: number;
};

export function listAuditLog(params: ListAuditLogParams = {}): Promise<AuditLogListResponse> {
  return apiFetch(`/administration/audit-log${buildQuery(params)}`);
}

export function getAuditLogEntry(id: number): Promise<AuditLogEntry> {
  return apiFetch(`/administration/audit-log/${id}`);
}

export type SystemHealth = {
  backend_status: string;
  database_status: string;
  api_status: string;
  ai_provider_status: string;
  app_version: string;
  environment: string;
};

export function getSystemHealth(): Promise<SystemHealth> {
  return apiFetch(`/administration/system-health`);
}

export type AIConfig = {
  provider: string;
  model: string | null;
  is_configured: boolean;
  status: string;
};

export function getAIConfig(): Promise<AIConfig> {
  return apiFetch(`/administration/ai-config`);
}

export type RoleCount = { role_name: string; user_count: number };

export type RecentAuditEvent = {
  id: number;
  action: string;
  entity_type: string | null;
  user_email: string | null;
  status: string;
  created_at: string;
};

export type AdminDashboard = {
  total_users: number;
  active_users: number;
  inactive_users: number;
  roles: RoleCount[];
  recent_activity: RecentAuditEvent[];
  system_status: string;
  configuration_status: string;
  ai_provider_configured: boolean;
};

export function getAdminDashboard(): Promise<AdminDashboard> {
  return apiFetch(`/administration/dashboard`);
}
