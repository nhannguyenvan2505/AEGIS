export interface UserRow {
  id: string; email: string; full_name: string | null; phone: string | null;
  role: string; status: 'active' | 'inactive' | 'locked'; last_login_at: string | null; created_at: string; farm_count: number;
}
export interface UserDetail {
  user: UserRow;
  farms: { id: string; name: string; address: string }[];
  recent_analyses: { id: string; status: string; model_version: string; created_at: string }[];
  activity: { action: string; entity_type: string | null; entity_id: string | null; created_at: string }[];
}
