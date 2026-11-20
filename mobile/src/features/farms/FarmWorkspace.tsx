import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from 'react';
import { uuid } from 'expo-modules-core';
import { useAuth } from '../../state/AuthContext';
import { useDemo } from '../../state/DemoContext';
import { ApiError } from '../../services/api';
import { initialPlots } from '../dashboard/mock';
import { farmClient, type Farm, type FarmValues, type FarmPlot, type FarmSeason, type PlotValues, type SeasonValues } from './client';

const demoFarm: Farm = { id: 'demo-farm', name: 'Nông trại trải nghiệm', address: '', manager: '', notes: '', version: 1,
  plot_count: initialPlots.length, area_ha: initialPlots.reduce((total, plot) => total + plot.area, 0), plots_without_area: 0 };
type Workspace = {
  farms: Farm[]; loaded: boolean; loading: boolean; error: string; busy: boolean; demo: boolean;
  selectedFarmId?: string; selectFarm: (id: string) => void; load: () => Promise<void>;
  loadPlots: (farmId: string) => Promise<FarmPlot[]>;
  loadSeasons: (plotId: string) => Promise<FarmSeason[]>;
  saveFarm: (values: FarmValues, farm?: Farm) => Promise<Farm>;
  deleteFarm: (farm: Farm) => Promise<void>;
  createPlot: (farmId: string, values: PlotValues) => Promise<FarmPlot>;
  createSeason: (plotId: string, values: SeasonValues) => Promise<FarmSeason>;
};
const Context = createContext<Workspace | null>(null);

function ScopedWorkspace({ token, children }: { token?: string; children: ReactNode }) {
  const { expireSession } = useAuth();
  const demo = !token;
  const [farms, setFarms] = useState<Farm[]>(() => demo ? [demoFarm] : []);
  const [demoPlots, setDemoPlots] = useState<FarmPlot[]>(() => demo ? initialPlots.map(plot => ({
    id: plot.id, farm_id: demoFarm.id, name: plot.name, location_text: '', area_ha: plot.area,
  })) : []);
  const [demoSeasons, setDemoSeasons] = useState<FarmSeason[]>(() => demo ? initialPlots.map(plot => ({
    id: `demo-season-${plot.id}`, plot_id: plot.id, name: plot.cycle, start_date: '', end_date: null,
  })) : []);
  const [selectedFarmId, selectFarm] = useState<string | undefined>(demo ? demoFarm.id : undefined);
  const [loaded, setLoaded] = useState(demo);
  const [loading, setLoading] = useState(!!token);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const writing = useRef(false);
  const readSequence = useRef(0);
  const active = useRef(true);
  useEffect(() => { active.current = true; return () => { active.current = false; }; }, []);

  const failure = useCallback((error: unknown) => {
    if (error instanceof ApiError && error.status === 401 && token) void expireSession(token).catch(() => {});
    return error instanceof Error ? error.message : 'Không thể tải dữ liệu. Vui lòng thử lại.';
  }, [token, expireSession]);

  const load = useCallback(() => {
    if (!token) return Promise.resolve();
    const sequence = ++readSequence.current;
    return farmClient.farms(token).then(result => {
      if (active.current && sequence === readSequence.current) {
        setFarms(result); setLoaded(true); setError('');
        selectFarm(current => result.some(farm => farm.id === current) ? current : result[0]?.id);
      }
    }).catch(error => { if (active.current && sequence === readSequence.current) setError(failure(error)); })
      .finally(() => { if (active.current && sequence === readSequence.current) setLoading(false); });
  }, [token, failure]);
  useEffect(() => { void load(); }, [load]);
  const refresh = useCallback(async () => { setLoading(true); setError(''); await load(); if (!token) setLoading(false); }, [load, token]);

  const loadPlots = useCallback(async (farmId: string) => {
    try { return token ? await farmClient.plots(token, farmId) : demoPlots.filter(plot => plot.farm_id === farmId); }
    catch (error) { failure(error); throw error; }
  }, [token, demoPlots, failure]);
  const loadSeasons = useCallback(async (plotId: string) => {
    try { return token ? await farmClient.seasons(token, plotId) : demoSeasons.filter(season => season.plot_id === plotId); }
    catch (error) { failure(error); throw error; }
  }, [token, demoSeasons, failure]);

  async function mutate<T,>(action: () => Promise<T>): Promise<T> {
    if (writing.current) throw new Error('Đang lưu dữ liệu. Vui lòng đợi.');
    writing.current = true; setBusy(true);
    readSequence.current++;
    try { return await action(); }
    catch (error) { failure(error); throw error; }
    finally { readSequence.current++; writing.current = false; if (active.current) { setBusy(false); setLoading(false); } }
  }

  function saveFarm(values: FarmValues, farm?: Farm) {
    return mutate(async () => {
      const item: Farm = token ? (await farmClient.save(token, values, farm)).item : {
        ...values, id: farm?.id ?? uuid.v4(), version: (farm?.version ?? 0) + 1,
        plot_count: farm?.plot_count ?? 0, area_ha: farm?.area_ha ?? 0, plots_without_area: farm?.plots_without_area ?? 0,
      };
      if (active.current) { setFarms(current => farm ? current.map(old => old.id === item.id ? item : old) : [item, ...current]); selectFarm(item.id); }
      return item;
    });
  }
  function deleteFarm(farm: Farm) {
    return mutate(async () => {
      if (farm.plot_count) throw new Error('Chỉ có thể xóa nông trại khi chưa có ruộng.');
      if (token) await farmClient.remove(token, farm);
      if (active.current) { setFarms(current => current.filter(item => item.id !== farm.id)); selectFarm(current => current === farm.id ? undefined : current); }
    });
  }
  function createPlot(farmId: string, values: PlotValues) {
    return mutate(async () => {
      const item: FarmPlot = token ? (await farmClient.createPlot(token, farmId, values)).item : { ...values, id: uuid.v4(), farm_id: farmId };
      if (active.current) {
        if (!token) setDemoPlots(current => [item, ...current]);
        setFarms(current => current.map(farm => farm.id === farmId ? { ...farm, plot_count: farm.plot_count + 1, area_ha: farm.area_ha + values.area_ha } : farm));
      }
      return item;
    });
  }
  function createSeason(plotId: string, values: SeasonValues) {
    return mutate(async () => {
      const item: FarmSeason = token ? (await farmClient.createSeason(token, plotId, values)).item : {
        ...values, id: uuid.v4(), plot_id: plotId, end_date: values.end_date || null,
      };
      if (!token && active.current) setDemoSeasons(current => [item, ...current]);
      return item;
    });
  }
  return <Context.Provider value={{ farms, loaded, loading, error, busy, demo, selectedFarmId, selectFarm,
    load: refresh, loadPlots, loadSeasons, saveFarm, deleteFarm, createPlot, createSeason }}>{children}</Context.Provider>;
}

export function FarmWorkspaceProvider({ children }: { children: ReactNode }) {
  const { session } = useAuth();
  const { generation } = useDemo();
  return <ScopedWorkspace key={session?.user.id ?? `demo-${generation}`} token={session?.access_token}>{children}</ScopedWorkspace>;
}
export function useFarmWorkspace() {
  const context = useContext(Context);
  if (!context) throw new Error('Missing FarmWorkspaceProvider');
  return context;
}
