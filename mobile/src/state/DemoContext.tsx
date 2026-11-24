import { createContext, useContext, useState } from 'react';
import { initialPlots } from '../features/dashboard/mock';
import type { Plot } from '../types/domain';
type DemoState = { plots: Plot[]; setPlots: (plots: Plot[]) => void; read: boolean; setRead: (read: boolean) => void; generation: number; reset: () => void };
const Context = createContext<DemoState | null>(null);
export function DemoProvider({ children }: { children: React.ReactNode }) {
 const [plots, setPlots] = useState(initialPlots); const [read, setRead] = useState(false);
 const [generation, setGeneration] = useState(0);
 return <Context.Provider value={{ plots, setPlots, read, setRead, generation, reset: () => { setPlots(initialPlots); setRead(false); setGeneration(value => value + 1); } }}>{children}</Context.Provider>;
}
export function useDemo() { const value = useContext(Context); if (!value) throw new Error('Missing DemoProvider'); return value; }
