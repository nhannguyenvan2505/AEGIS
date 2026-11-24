import { useCallback, useRef, useState } from 'react';
import { useFocusEffect, useLocalSearchParams } from 'expo-router';

export function useFarmIds() {
  const params = useLocalSearchParams<{ farmId?: string; plotId?: string }>();
  return { farmId: typeof params.farmId === 'string' ? params.farmId : '', plotId: typeof params.plotId === 'string' ? params.plotId : '' };
}

export function useFarmActionFocus() {
  const focused = useRef(false);
  useFocusEffect(useCallback(() => {
    focused.current = true;
    return () => { focused.current = false; };
  }, []));
  return useCallback(() => focused.current, []);
}

export function useFarmData<T>(loader: () => Promise<T>) {
  const [state, setState] = useState<{ data?: T; loading: boolean; error: string }>({ loading: true, error: '' });
  const sequence = useRef(0);
  const reload = useCallback(() => {
    const current = ++sequence.current;
    // Stale-while-revalidate: keep showing existing data instead of flashing a spinner on every focus.
    setState(state => ({ ...state, loading: state.data === undefined, error: '' }));
    void loader().then(data => { if (sequence.current === current) setState({ data, loading: false, error: '' }); })
      .catch(error => { if (sequence.current === current) setState({ loading: false, error: error instanceof Error ? error.message : 'Không tải được dữ liệu.' }); });
  }, [loader]);
  useFocusEffect(useCallback(() => { reload(); return () => { sequence.current++; }; }, [reload]));
  return { ...state, reload };
}
