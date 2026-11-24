import { lazy, Suspense } from 'react';
import { createBrowserRouter, Navigate, type RouteObject } from 'react-router-dom';
import { RequireRole } from '../core/auth/RequireRole';
import { LoadingState } from '../shared/feedback/Feedback';
import { AppShell } from '../shared/layout/AppShell';
import { ForbiddenPage, NotFoundPage } from '../pages/StatusPages';

// Mỗi feature được tải khi cần (lazy) để bundle đầu nhỏ.
const LoginPage = lazy(() => import('../features/auth/pages/LoginPage'));
const DashboardPage = lazy(() => import('../features/stats/pages/DashboardPage'));
const UserListPage = lazy(() => import('../features/users/pages/UserListPage'));
const UserDetailPage = lazy(() => import('../features/users/pages/UserDetailPage'));
const FarmListPage = lazy(() => import('../features/farms/pages/FarmPages').then((m) => ({ default: m.FarmListPage })));
const FarmDetailPage = lazy(() => import('../features/farms/pages/FarmPages').then((m) => ({ default: m.FarmDetailPage })));
const PlotDetailPage = lazy(() => import('../features/farms/pages/FarmPages').then((m) => ({ default: m.PlotDetailPage })));
const SeasonDetailPage = lazy(() => import('../features/farms/pages/FarmPages').then((m) => ({ default: m.SeasonDetailPage })));
const DeviceListPage = lazy(() => import('../features/devices/pages/DevicePages').then((m) => ({ default: m.DeviceListPage })));
const DeviceDetailPage = lazy(() => import('../features/devices/pages/DevicePages').then((m) => ({ default: m.DeviceDetailPage })));
const DetectionListPage = lazy(() => import('../features/detections/pages/DetectionPages').then((m) => ({ default: m.DetectionListPage })));
const DetectionDetailPage = lazy(() => import('../features/detections/pages/DetectionPages').then((m) => ({ default: m.DetectionDetailPage })));
const AlertsPage = lazy(() => import('../features/alerts/pages/AlertPages'));
const ThresholdPage = lazy(() => import('../features/thresholds/pages/ThresholdPage'));
const KnowledgePage = lazy(() => import('../features/knowledge/pages/KnowledgePage'));
const ModelPage = lazy(() => import('../features/models/pages/ModelPage'));
const HealthPage = lazy(() => import('../features/system/pages/SystemPages').then((m) => ({ default: m.HealthPage })));
const SettingsPage = lazy(() => import('../features/system/pages/SystemPages').then((m) => ({ default: m.SettingsPage })));
const AuditPage = lazy(() => import('../features/system/pages/SystemPages').then((m) => ({ default: m.AuditPage })));

const wrap = (el: React.ReactElement) => <Suspense fallback={<LoadingState />}>{el}</Suspense>;

export const routes: RouteObject[] = [
  { path: '/login', element: wrap(<LoginPage />) },
  {
    element: <RequireRole />,
    children: [{
      element: <AppShell />,
      children: [
        { index: true, element: <Navigate to="/dashboard" replace /> },
        { path: 'dashboard', element: wrap(<DashboardPage />) },
        { path: 'farms', element: wrap(<FarmListPage />) }, { path: 'farms/:id', element: wrap(<FarmDetailPage />) },
        { path: 'plots/:id', element: wrap(<PlotDetailPage />) }, { path: 'seasons/:id', element: wrap(<SeasonDetailPage />) },
        { path: 'devices', element: wrap(<DeviceListPage />) }, { path: 'devices/:id', element: wrap(<DeviceDetailPage />) },
        { path: 'detections', element: wrap(<DetectionListPage />) }, { path: 'detections/:id', element: wrap(<DetectionDetailPage />) },
        { path: 'alerts', element: wrap(<AlertsPage />) }, { path: 'thresholds', element: wrap(<ThresholdPage />) },
        { path: 'knowledge', element: wrap(<KnowledgePage />) }, { path: 'models', element: wrap(<ModelPage />) },
        // Chỉ admin.
        { element: <RequireRole roles={['admin']} />, children: [
          { path: 'users', element: wrap(<UserListPage />) }, { path: 'users/:id', element: wrap(<UserDetailPage />) },
          { path: 'system/health', element: wrap(<HealthPage />) }, { path: 'system/settings', element: wrap(<SettingsPage />) }, { path: 'audit', element: wrap(<AuditPage />) },
        ] },
      ],
    }],
  },
  { path: '/403', element: <ForbiddenPage /> },
  { path: '*', element: <NotFoundPage /> },
];

export const router = createBrowserRouter(routes);
