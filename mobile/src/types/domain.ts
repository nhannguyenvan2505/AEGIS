export type Role = 'farmer' | 'admin';
export interface Session { access_token: string; expires_at?: number; user: { id: string; email: string } }
export interface Plot { id: string; name: string; area: number; crop: string; cycle: string }
export interface Telemetry { temperature: number; humidity: number; soilMoisture: number; ph: number; recordedAt: string; source: 'iot' | 'manual' | 'historical' }
export interface Prediction { disease: string; probability: number; source: string }

export interface Analysis { analysis_id: string; created_at: string; status: string; model_version: string; detections: { disease: string; confidence: number; bbox: { x1: number; y1: number; x2: number; y2: number } }[] }
export interface HistoryPage { items: { analysis_id: string; created_at: string; status: string; detection_count: number }[]; pagination: { page: number; has_next: boolean } }
