import { request } from '../../services/api';

export type State = 'open' | 'acknowledged' | 'checked' | 'closed';
export type Page<T> = { items: T[]; pagination: { page: number; page_size: number; total: number; total_pages: number; has_next: boolean } };
export type Named = { id: string; name: string };
export type Case = { id: string; season_id: string; state: State; version: number; task_kind: string; check_status: { needs_recheck: boolean; reasons: string[] } };
export type Observation = { id: string; source: string; observed_at: string; revision: number; payload: { record_status: string; finding: string } };
export type Version = { id: string; revision: number; display_freshness: string; available_at: string; snapshot: { result: { status: string; window_end: string } } };
type Eligibility = { enabled: boolean; disabled_reasons: string[] };
export type Projection = { projection_version: string; base_version: number; validation_scope: string;
  actions: { acknowledge: Eligibility; check: Eligibility & { observation_required: boolean; observation_constraints: { source: string; record_status: string; observed_at_not_before: string; selection_validated: boolean } } };
  needs_recheck: boolean; recheck_reasons: string[] };
export type View = { followup_id: string; followup_version: number; required: Version; current: Version; action_capabilities?: Projection };
export type Command = { client_event_id: string; base_version: number; action: 'acknowledge' | 'check'; reason: string; observation_id: string | null; resolution: null };
export type CommandResult = { item: Case; event: { id: string; version: number } };
const id = encodeURIComponent;
function get<T>(path: string, token: string) {
  return request<T>(path, {}, token, 15000, 'Hết thời gian chờ tải công việc. Hãy tải lại.');
}
export const followupClient = {
  capabilities: (token: string) => get<{ mode: string; follow_up: { available: boolean; source: string } }>('/mobile/capabilities', token),
  plots: (token: string, page: number) => get<Page<Named>>(`/farm/plots?page=${page}&page_size=20`, token),
  seasons: (token: string, plot: string, page: number) => get<Page<Named>>(`/farm/plots/${id(plot)}/seasons?page=${page}&page_size=20`, token),
  cases: (token: string, season: string, page: number, state: State | '') => get<Page<Case>>(`/farm/seasons/${id(season)}/follow-ups?page=${page}&page_size=20${state ? `&state=${state}` : ''}`, token),
  detail: (token: string, caseId: string) => get<{ item: Case }>(`/farm/follow-ups/${id(caseId)}`, token),
  view: (token: string, caseId: string) => get<{ item: View }>(`/farm/follow-ups/${id(caseId)}/assessment-view`, token),
  observations: (token: string, season: string, page: number) => get<Page<Observation>>(`/farm/seasons/${id(season)}/observations?page=${page}&page_size=20`, token),
  command: (token: string, caseId: string, command: Command) => request<CommandResult>(`/farm/follow-ups/${id(caseId)}/events`, { method: 'POST', body: JSON.stringify(command) }, token, 15000,
    'Chưa biết thao tác đã được ghi hay chưa. Giữ ý định và gửi lại nguyên bản khi kết nối ổn định.'),
};

export function projection(view?: View): Projection | undefined {
  const p = view?.action_capabilities;
  if (!p || p.projection_version !== 'aegis-followup-actions-v1' || p.base_version !== view?.followup_version || p.validation_scope !== 'workflow_state_and_declared_inputs') return;
  if (typeof p.actions?.acknowledge?.enabled !== 'boolean' || typeof p.actions?.check?.enabled !== 'boolean' || typeof p.actions.check.observation_required !== 'boolean') return;
  const c = p.actions.check.observation_constraints;
  if (!c || c.source !== 'synthetic' || c.record_status !== 'active' || c.selection_validated !== false || !Number.isFinite(Date.parse(c.observed_at_not_before))) return;
  if (!Array.isArray(p.actions.acknowledge.disabled_reasons) || !Array.isArray(p.actions.check.disabled_reasons) || !Array.isArray(p.recheck_reasons) || typeof p.needs_recheck !== 'boolean') return;
  return p;
}

export function eligibleObservation(o: Observation, p: Projection) {
  const c = p.actions.check.observation_constraints;
  return o.source === c.source && o.payload.record_status === c.record_status && Number.isFinite(Date.parse(o.observed_at)) && Date.parse(o.observed_at) >= Date.parse(c.observed_at_not_before);
}
