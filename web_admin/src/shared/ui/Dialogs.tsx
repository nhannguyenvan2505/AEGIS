import * as Dialog from '@radix-ui/react-dialog';
import { useState, type ReactNode } from 'react';
import { ApiError } from '../../core/api/errors';

export function Modal({ open, onClose, title, children }: { open: boolean; onClose(): void; title: string; children: ReactNode }) {
  return (
    <Dialog.Root open={open} onOpenChange={(o) => { if (!o) onClose(); }}>
      <Dialog.Portal>
        <Dialog.Overlay className="overlay" />
        <Dialog.Content className="dialog" aria-describedby={undefined}>
          <Dialog.Title asChild><h2>{title}</h2></Dialog.Title>
          {children}
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}

/** Xác nhận cho mọi thao tác nguy hiểm (khóa, vô hiệu hóa, xóa, kích hoạt mô hình...). */
export function ConfirmDialog({ open, title, message, confirmLabel = 'Xác nhận', danger, onConfirm, onClose }: {
  open: boolean; title: string; message: ReactNode; confirmLabel?: string; danger?: boolean;
  onConfirm(): Promise<unknown> | void; onClose(): void;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const run = async () => {
    setBusy(true); setError(null);
    try { await onConfirm(); onClose(); } catch (e) { setError(e); } finally { setBusy(false); }
  };
  return (
    <Modal open={open} onClose={onClose} title={title}>
      <div>{message}</div>
      {error !== null && <div className="error-box" role="alert">{error instanceof ApiError ? error.message : 'Đã xảy ra lỗi.'}</div>}
      <div className="dialog-actions">
        <button className="btn secondary" onClick={onClose} disabled={busy}>Hủy</button>
        <button className={`btn${danger ? ' danger' : ''}`} onClick={run} disabled={busy}>{busy ? 'Đang xử lý…' : confirmLabel}</button>
      </div>
    </Modal>
  );
}

export type FieldType = 'text' | 'password' | 'number' | 'select' | 'textarea' | 'checkbox' | 'datetime';
export interface FieldDef {
  name: string; label: string; type?: FieldType; required?: boolean; placeholder?: string;
  options?: { value: string; label: string }[]; help?: string;
}
export type FormValues = Record<string, string | boolean>;

/** Form tổng quát: backend kiểm tra dữ liệu thật (422/409); lỗi của backend hiển thị nguyên văn ngay trong hộp thoại. */
export function FormDialog({ open, title, fields, initial, submitLabel = 'Lưu', onSubmit, onClose, extraAction }: {
  open: boolean; title: string; fields: FieldDef[]; initial?: FormValues; submitLabel?: string;
  onSubmit(values: FormValues): Promise<unknown>; onClose(): void;
  /** Nút phụ cạnh nút Lưu (ví dụ "Chạy thử"); kết quả trả về hiển thị dưới form. */
  extraAction?: { label: string; run(values: FormValues): Promise<string> };
}) {
  const [values, setValues] = useState<FormValues>(() => initial ?? {});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [info, setInfo] = useState<string | null>(null);

  const runExtra = async () => {
    setBusy(true); setError(null); setInfo(null);
    try { setInfo(await extraAction!.run(values)); } catch (e) { setError(e); } finally { setBusy(false); }
  };

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setBusy(true); setError(null);
    try { await onSubmit(values); onClose(); } catch (e) { setError(e); } finally { setBusy(false); }
  };
  const set = (name: string, value: string | boolean) => setValues((v) => ({ ...v, [name]: value }));

  return (
    <Modal open={open} onClose={onClose} title={title}>
      <form onSubmit={submit} className="stack" style={{ gap: 12 }}>
        {fields.map((f) => {
          const id = `f-${f.name}`;
          const type = f.type ?? 'text';
          if (type === 'checkbox') {
            return <label key={f.name} className="field check"><input type="checkbox" checked={Boolean(values[f.name])} onChange={(e) => set(f.name, e.target.checked)} />{f.label}</label>;
          }
          return (
            <label key={f.name} className="field" htmlFor={id}>
              {f.label}{f.required && ' *'}
              {type === 'select' ? (
                <select id={id} value={String(values[f.name] ?? '')} required={f.required} onChange={(e) => set(f.name, e.target.value)}>
                  {!f.required && <option value="">—</option>}
                  {f.options?.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
                </select>
              ) : type === 'textarea' ? (
                <textarea id={id} value={String(values[f.name] ?? '')} required={f.required} placeholder={f.placeholder} onChange={(e) => set(f.name, e.target.value)} />
              ) : (
                <input id={id} type={type === 'datetime' ? 'datetime-local' : type} step={type === 'number' ? 'any' : undefined} value={String(values[f.name] ?? '')}
                  required={f.required} placeholder={f.placeholder} autoComplete="off" onChange={(e) => set(f.name, e.target.value)} />
              )}
              {f.help && <span className="small muted" style={{ fontWeight: 400 }}>{f.help}</span>}
            </label>
          );
        })}
        {info && <div className="notice" role="status">{info}</div>}
        {error !== null && <div className="error-box" role="alert">{error instanceof ApiError ? error.message : 'Đã xảy ra lỗi.'}</div>}
        <div className="dialog-actions">
          {extraAction && <button type="button" className="btn secondary" onClick={() => void runExtra()} disabled={busy}>{extraAction.label}</button>}
          <button type="button" className="btn secondary" onClick={onClose} disabled={busy}>Hủy</button>
          <button type="submit" className="btn" disabled={busy}>{busy ? 'Đang lưu…' : submitLabel}</button>
        </div>
      </form>
    </Modal>
  );
}
