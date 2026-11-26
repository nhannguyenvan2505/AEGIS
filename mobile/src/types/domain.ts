export type Role = 'farmer' | 'admin';
export interface Session { access_token: string; expires_at?: number; user: { id: string; email: string } }
export interface Plot { id: string; name: string; area: number; crop: string; cycle: string }
export interface Telemetry { temperature: number; humidity: number; soilMoisture: number; ph: number; recordedAt: string; source: 'iot' | 'manual' | 'historical' }
export interface Prediction { disease: string; probability: number; source: string }

export type Rejection = 'rejected_non_rice' | 'rejected_poor_quality' | 'rejected_uncertain_scope';
// Domain rejection (HTTP 200, not stored): analysis_id/created_at are absent and `rejected` is true.
export interface Analysis { analysis_id: string; created_at: string; status: string; model_version: string; rejected?: boolean; message?: string; is_rice?: boolean | null; diagnosis?: { status: string; message?: string }; detections: { disease: string; confidence: number; bbox: { x1: number; y1: number; x2: number; y2: number } }[] }
export interface HistoryPage { items: { analysis_id: string; created_at: string; status: string; detection_count: number }[]; pagination: { page: number; has_next: boolean } }
