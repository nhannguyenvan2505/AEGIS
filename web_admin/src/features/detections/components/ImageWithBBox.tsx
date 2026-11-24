import { useEffect, useState } from 'react';
import { apiBlobUrl } from '../../../core/api/client';
import { ErrorState, LoadingState } from '../../../shared/feedback/Feedback';
import type { BBox } from '../types';

/**
 * Ảnh chẩn đoán cần Bearer nên tải qua fetch -> blob URL (thẻ img thường không gửi được header).
 * Khung vẽ theo phần trăm của kích thước gốc nên co giãn đúng khi ảnh bị thu nhỏ.
 */
export function ImageWithBBox({ path, width, height, bbox, label }: { path: string; width: number; height: number; bbox: BBox | null; label: string }) {
  const [src, setSrc] = useState<string | null>(null);
  const [error, setError] = useState<unknown>(null);

  useEffect(() => {
    const controller = new AbortController();
    let url: string | null = null;
    apiBlobUrl(path.replace(/^\/api\/admin/, ''), controller.signal)
      .then((u) => { url = u; setSrc(u); })
      .catch((e) => { if ((e as Error).name !== 'AbortError') setError(e); });
    return () => { controller.abort(); if (url) URL.revokeObjectURL(url); };
  }, [path]);

  if (error) return <ErrorState error={error} />;
  if (!src) return <LoadingState rows={3} />;
  const box = bbox && width > 0 && height > 0 ? {
    left: `${(bbox.x1 / width) * 100}%`, top: `${(bbox.y1 / height) * 100}%`,
    width: `${((bbox.x2 - bbox.x1) / width) * 100}%`, height: `${((bbox.y2 - bbox.y1) / height) * 100}%`,
  } : null;
  return (
    <div className="bbox-wrap">
      <img src={src} alt={`Ảnh lá lúa: ${label}`} />
      {box && <div className="box" style={box}><span className="tag">{label}</span></div>}
    </div>
  );
}
