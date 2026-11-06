import { ApiError } from '../../services/api';
import { followupClient, eligibleObservation, projection, type Case, type Command, type Named, type Observation, type Page, type State, type View } from './client';

type Pending = { caseId: string; body: Command };
export type Model = { busy: boolean; available: boolean; error: string; message: string; retryAt: number;
  plot: string; season: string; caseId: string; filter: State | ''; plots?: Page<Named>; seasons?: Page<Named>;
  cases?: Page<Case>; detail?: Case; view?: View; observations?: Page<Observation>; selected: string; reason: string; pending?: Pending };

export class FollowupController {
  state: Model = { busy: false, available: false, error: '', message: '', retryAt: 0, plot: '', season: '', caseId: '', filter: '', selected: '', reason: '' };
  private generation = 0;
  private alive = true;
  constructor(private token: string, private changed: (state: Model) => void, private unauthorized: () => void,
    private uuid: () => string, private api = followupClient) {}
  private update(patch: Partial<Model>) { if (this.alive) { this.state = { ...this.state, ...patch }; this.changed(this.state); } }
  activate() { this.alive = true; this.generation++; this.state = { ...this.state, busy: false }; }
  dispose() { this.alive = false; this.generation++; this.state = { ...this.state, pending: undefined, view: undefined, detail: undefined, observations: undefined }; }
  edit(reason: string, selected = this.state.selected) { if (!this.state.pending && !this.state.busy) this.update({ reason, selected }); }
  private reset(patch: Partial<Model>) {
    this.generation++; this.update({ busy: false, error: '', message: '', detail: undefined, view: undefined, observations: undefined,
      selected: '', reason: '', ...patch });
  }
  private async run(work: () => Promise<void>) {
    if (!this.alive || this.state.busy || Date.now() < this.state.retryAt) return;
    const generation = this.generation;
    this.update({ busy: true, error: '' });
    try { await work(); }
    catch (error) { if (this.alive && generation === this.generation) this.failure(error); }
    finally { if (this.alive && generation === this.generation) this.update({ busy: false }); }
  }
  private current(g: number) { return this.alive && g === this.generation; }
  private failure(error: unknown) {
    if (error instanceof ApiError && error.status === 401) {
      this.reset({ available: false, plots: undefined, seasons: undefined, cases: undefined, plot: '', season: '', caseId: '', pending: undefined, error: 'Phiên đã hết hiệu lực. Đăng nhập lại.' });
      this.unauthorized(); return;
    }
    let retryAt = this.state.retryAt;
    if (error instanceof ApiError && error.status === 429) {
      const value = error.retryAfter; const seconds = Number(value);
      retryAt = value && Number.isFinite(seconds) ? Date.now() + Math.max(0, seconds) * 1000 : Date.parse(value ?? '') || Date.now() + 1000;
    }
    const message = error instanceof Error ? error.message : 'Không thể tải công việc.';
    this.update({ error: message + (error instanceof ApiError && error.requestId ? ` · Mã hỗ trợ: ${error.requestId}` : ''), retryAt });
  }
  async start() {
    await this.run(async () => {
      const g = this.generation; const c = await this.api.capabilities(this.token);
      if (!this.current(g)) return;
      if (c.mode !== 'pilot' || !c.follow_up.available || c.follow_up.source !== 'mock') {
        this.update({ available: false, error: 'Backend hiện tại không có follow-up pilot. Kiểm tra origin và kho dữ liệu.' }); return;
      }
      this.update({ available: true }); const plots = await this.api.plots(this.token, 1);
      if (this.current(g)) this.update({ plots });
    });
  }
  async loadPlots(page: number) {
    if (!this.state.available || this.state.pending) return;
    await this.run(async () => { const g = this.generation; const plots = await this.api.plots(this.token, page); if (this.current(g)) this.update({ plots }); });
  }
  async choosePlot(plot: string, page = 1) {
    if (!this.state.available || this.state.pending) return;
    this.reset({ plot, season: '', caseId: '', seasons: undefined, cases: undefined });
    await this.run(async () => { const g = this.generation; const seasons = await this.api.seasons(this.token, plot, page); if (this.current(g)) this.update({ seasons }); });
  }
  async chooseSeason(season: string, filter: State | '' = this.state.filter, page = 1) {
    if (!this.state.available || this.state.pending) return;
    this.reset({ season, filter, caseId: '', cases: undefined });
    await this.run(async () => { const g = this.generation; const cases = await this.api.cases(this.token, season, page, filter); if (this.current(g)) this.update({ cases }); });
  }
  private async readDetail(g: number, caseId: string, season: string) {
    const [detail, view, observations] = await Promise.all([this.api.detail(this.token, caseId), this.api.view(this.token, caseId), this.api.observations(this.token, season, 1)]);
    if (this.current(g)) {
      if (detail.item.season_id !== season || view.item.followup_id !== caseId) throw new Error('Bối cảnh response không khớp. Tải lại.');
      if (detail.item.version !== view.item.followup_version) throw new Error('Công việc vừa thay đổi. Tải lại trước khi thao tác.');
      this.update({ detail: detail.item, view: view.item, observations, selected: '' });
    }
  }
  async open(caseId: string) {
    if (!this.state.available || !this.state.season || this.state.pending) return;
    this.reset({ caseId });
    await this.run(async () => this.readDetail(this.generation, caseId, this.state.season));
  }
  async refresh() {
    if (!this.state.caseId || this.state.busy || Date.now() < this.state.retryAt) return;
    // Clear previous snapshots so an integrity/read error cannot leave actions available.
    this.update({ detail: undefined, view: undefined, observations: undefined, selected: '' });
    await this.run(async () => this.readDetail(this.generation, this.state.caseId, this.state.season));
  }
  async loadObservations(page: number) {
    if (this.state.pending || !this.state.view) return;
    await this.run(async () => { const g = this.generation; const observations = await this.api.observations(this.token, this.state.season, page); if (this.current(g)) this.update({ observations, selected: '' }); });
  }
  async act(action: Command['action']) {
    if (this.state.pending || this.state.busy) return;
    const p = projection(this.state.view); const reason = this.state.reason.trim();
    if (!p || !p.actions[action].enabled || !reason || reason.length > 500 || Date.now() < this.state.retryAt) return;
    const observation = this.state.observations?.items.find(o => o.id === this.state.selected);
    if (action === 'check' && (p.actions.check.observation_required || this.state.selected) && (!observation || !eligibleObservation(observation, p))) {
      this.update({ error: 'Chọn quan sát synthetic active đúng mốc yêu cầu; server vẫn kiểm tra lại.' }); return;
    }
    let clientEventId: string;
    try { clientEventId = this.uuid(); } catch { this.update({ error: 'Không tạo được mã thao tác. Chưa gửi dữ liệu; hãy khởi động lại ứng dụng.' }); return; }
    this.update({ pending: { caseId: this.state.caseId, body: { client_event_id: clientEventId, base_version: p.base_version,
      action, reason, observation_id: action === 'check' ? this.state.selected || null : null, resolution: null } } });
    await this.retry();
  }
  async retry() {
    if (!this.state.pending) return;
    await this.run(async () => {
      const g = this.generation; const pending = this.state.pending!; const season = this.state.season;
      try { await this.api.command(this.token, pending.caseId, pending.body); }
      catch (error) {
        if (!this.current(g)) return;
        if (error instanceof ApiError && error.status >= 400 && error.status < 500 && error.status !== 429) {
          this.update({ pending: undefined, view: undefined, detail: undefined, observations: undefined });
          if (error.status === 409) {
            this.update({ message: 'Công việc đã thay đổi. Đọc bản mới và tự quyết định ý định mới; không tự gửi lại.' });
            await this.readDetail(g, pending.caseId, season);
          }
        }
        throw error;
      }
      if (!this.current(g)) return;
      this.update({ pending: undefined, reason: '', view: undefined, detail: undefined, observations: undefined,
        message: 'Đã ghi nhận thao tác. Đang đọc lại trạng thái hiện tại.' });
      await this.readDetail(g, pending.caseId, season);
    });
  }
}
