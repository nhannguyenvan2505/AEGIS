import type { Role } from '../core/auth/AuthContext';
import type { IconName } from '../shared/ui/Icon';

export interface NavItem { label: string; to: string; roles: Role[]; icon: IconName }
export interface NavGroup { title: string; items: NavItem[] }

/** Menu và vai trò được thấy (khớp ma trận quyền ở backend; backend mới là nơi chặn thật). */
export const NAV: NavGroup[] = [
  { title: 'Tổng quan', items: [{ label: 'Dashboard', to: '/dashboard', roles: ['admin'], icon: 'dashboard' }] },
  {
    title: 'Vận hành',
    items: [
      { label: 'Người dùng', to: '/users', roles: ['admin'], icon: 'users' },
      { label: 'Nông trại', to: '/farms', roles: ['admin'], icon: 'sprout' },
      { label: 'Thiết bị IoT', to: '/devices', roles: ['admin'], icon: 'cpu' },
      { label: 'Cảnh báo', to: '/alerts', roles: ['admin'], icon: 'bell' },
    ],
  },
  {
    title: 'Dữ liệu AI',
    items: [
      { label: 'Chẩn đoán', to: '/detections', roles: ['admin'], icon: 'scan' },
      { label: 'Ngưỡng cảnh báo', to: '/thresholds', roles: ['admin'], icon: 'sliders' },
      { label: 'Bệnh & khuyến nghị', to: '/knowledge', roles: ['admin'], icon: 'book' },
      { label: 'Mô hình AI', to: '/models', roles: ['admin'], icon: 'layers' },
    ],
  },
  {
    title: 'Hệ thống',
    items: [
      { label: 'Sức khỏe', to: '/system/health', roles: ['admin'], icon: 'pulse' },
      { label: 'Cấu hình', to: '/system/settings', roles: ['admin'], icon: 'settings' },
      { label: 'Nhật ký', to: '/audit', roles: ['admin'], icon: 'scroll' },
    ],
  },
];

/** Route chỉ-admin không nằm hết trong menu (trang chi tiết), nên liệt kê theo tiền tố. */
const ADMIN_ONLY_PREFIXES = ['/users', '/system', '/audit'];

/** Vai trò này có được vào đường dẫn này không (dùng để quyết định quay lại trang cũ sau khi đăng nhập). */
export function canAccess(path: string, role: Role): boolean {
  const clean = path.split('?')[0];
  if (ADMIN_ONLY_PREFIXES.some((p) => clean === p || clean.startsWith(`${p}/`))) return role === 'admin';
  return true;
}
