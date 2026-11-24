// Mọi trạng thái đều kèm chữ (không chỉ màu) để dễ đọc với người khó phân biệt màu.
type Tone = '' | 'warn' | 'danger' | 'info' | 'neutral';

function Badge({ tone = '', children }: { tone?: Tone; children: React.ReactNode }) {
  return <span className={`badge ${tone}`.trim()}>{children}</span>;
}

const USER_STATUS: Record<string, [string, Tone]> = { active: ['Hoạt động', ''], inactive: ['Vô hiệu hóa', 'neutral'], locked: ['Bị khóa', 'danger'] };
export const UserStatusBadge = ({ value }: { value: string }) => <Badge tone={USER_STATUS[value]?.[1]}>{USER_STATUS[value]?.[0] ?? value}</Badge>;

export const RoleBadge = ({ value }: { value: string }) => <Badge tone={value === 'admin' ? 'info' : 'neutral'}>{value}</Badge>;

const DEVICE: Record<string, [string, Tone]> = { online: ['Online', ''], offline: ['Offline', 'danger'], maintenance: ['Bảo trì', 'warn'], inactive: ['Ngừng', 'neutral'] };
export const DeviceStatusBadge = ({ value }: { value: string }) => <Badge tone={DEVICE[value]?.[1]}>{DEVICE[value]?.[0] ?? value}</Badge>;

const SEVERITY: Record<string, [string, Tone]> = { info: ['Thông tin', 'info'], warning: ['Cảnh báo', 'warn'], high: ['Cao', 'danger'], critical: ['Nghiêm trọng', 'danger'] };
export const SeverityBadge = ({ value }: { value: string }) => <Badge tone={SEVERITY[value]?.[1]}>{SEVERITY[value]?.[0] ?? value}</Badge>;

const ALERT: Record<string, [string, Tone]> = { open: ['Đang mở', 'danger'], acknowledged: ['Đã ghi nhận', 'warn'], resolved: ['Đã xử lý', ''] };
export const AlertStatusBadge = ({ value }: { value: string }) => <Badge tone={ALERT[value]?.[1]}>{ALERT[value]?.[0] ?? value}</Badge>;

const DELIVERY: Record<string, [string, Tone]> = { pending: ['Chờ gửi', 'warn'], sent: ['Đã gửi', ''], failed: ['Lỗi', 'danger'] };
export const DeliveryBadge = ({ value }: { value: string }) => <Badge tone={DELIVERY[value]?.[1]}>{DELIVERY[value]?.[0] ?? value}</Badge>;

export const ActiveBadge = ({ value }: { value: boolean | number }) => <Badge tone={value ? '' : 'neutral'}>{value ? 'Bật' : 'Tắt'}</Badge>;
export const SourceTag = ({ source }: { source: string }) => <Badge tone={source === 'mock' || source === 'synthetic' ? 'warn' : 'info'}>{source === 'mock' || source === 'synthetic' ? `Mô phỏng (${source})` : source}</Badge>;

export const DISEASE_LABEL: Record<string, string> = { rice_blast: 'Đạo ôn', brown_spot: 'Đốm nâu', sheath_blight: 'Khô vằn' };
export const DiseaseBadge = ({ value }: { value: string }) => <Badge tone="danger">{DISEASE_LABEL[value] ?? value}</Badge>;

export const SENSOR_LABEL: Record<string, string> = { temperature: 'Nhiệt độ', humidity: 'Độ ẩm không khí', soil_ph: 'pH đất', rainfall: 'Lượng mưa' };
export const SENSOR_OPTIONS = Object.entries(SENSOR_LABEL).map(([value, label]) => ({ value, label }));
export const SensorTag = ({ value }: { value: string | null }) => value ? <Badge tone="info">{SENSOR_LABEL[value] ?? value}</Badge> : <Badge tone="neutral">Chưa phân loại</Badge>;
