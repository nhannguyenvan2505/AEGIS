export interface DetectionRow {
  id: string; analysis_id: string; class_id: number; disease: string; confidence: number;
  created_at: string; model_version: string;
  ai_processing_ms: number | null; request_id: string | null; user_id: string; user_email: string; user_name?: string | null;
}
export interface DetectionDetail extends DetectionRow {
  bbox: unknown; source_confidence: number; image_width: number; image_height: number; orientation: string;
  analysis_status: string; model_sha256: string; image_url: string;
}
export interface BBox { x1: number; y1: number; x2: number; y2: number }
