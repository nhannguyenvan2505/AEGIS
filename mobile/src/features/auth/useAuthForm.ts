import { useCallback, useRef, useState } from 'react';
import { useFocusEffect } from 'expo-router';
import { Keyboard } from 'react-native';
import type { FieldErrors } from './validation';

export function useAuthForm<T extends Record<string, string>>(
  initialValues: T,
  validate: (values: T) => FieldErrors<T>,
  onValid: (values: T) => void | Promise<void>,
) {
  const [values, setValues] = useState(initialValues);
  const submitting = useRef(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [submitted, setSubmitted] = useState(false);
  const errors = submitted ? validate(values) : {} as FieldErrors<T>;

  const reset = useCallback(() => {
    setValues(initialValues);
    setSubmitted(false);
  }, [initialValues]);

  // Stack routes can remain mounted. Clear sensitive fields when leaving a form.
  useFocusEffect(useCallback(() => reset, [reset]));

  function setField(field: keyof T, value: string) {
    setValues(current => ({ ...current, [field]: value }));
  }

  async function submit() {
    if (submitting.current) return;
    setSubmitted(true);
    Keyboard.dismiss();
    if (Object.values(validate(values)).some(Boolean)) return;
    submitting.current = true; setBusy(true); setError('');
    try { await onValid(values); reset(); }
    catch (err) { setError(err instanceof Error ? err.message : 'Không thể kết nối Backend.'); }
    finally { submitting.current = false; setBusy(false); }
  }

  return { values, errors, setField, submit, busy, error };
}
