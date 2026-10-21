"use client";
import { useId, useRef, useState, type ReactNode } from "react";
import { Minus, Plus, RotateCcw, X, ZoomIn } from "lucide-react";

export function CandidatePortrait({candidateId, name, variant = "list", fallback = null}: {
  candidateId: string; name: string; variant?: "list" | "profile"; fallback?: ReactNode;
}) {
  const [failed, setFailed] = useState(false);
  const [open, setOpen] = useState(false);
  const [zoom, setZoom] = useState(1);
  const dialog = useRef<HTMLDialogElement>(null);
  const titleId = useId();
  const source = `/api/backend/candidates/${candidateId}/photo`;
  if (failed) return fallback;
  function show() {
    setZoom(1); setOpen(true); dialog.current?.showModal();
  }
  // Native images carry the session cookie to our authenticated BFF. Next's
  // image optimizer does not forward cookies to protected sources.
  /* eslint-disable @next/next/no-img-element */
  return <>
    <button type="button" className={`portrait-trigger portrait-trigger-${variant}`}
      aria-label={`Phóng to ảnh chân dung ${name}`} aria-haspopup="dialog" onClick={show}>
      <img className="candidate-portrait" src={source} alt={`Ảnh chân dung ${name}`}
        width={variant === "profile" ? 112 : 96} height={variant === "profile" ? 140 : 112}
        loading={variant === "profile" ? "eager" : "lazy"} decoding="async" onError={() => setFailed(true)}/>
      <span className="portrait-zoom-hint" aria-hidden="true"><ZoomIn size={14}/></span>
    </button>
    <dialog ref={dialog} className="portrait-dialog" aria-labelledby={titleId}
      onClose={() => setOpen(false)} onClick={event => {if (event.target === event.currentTarget) dialog.current?.close();}}>
      <header className="portrait-dialog-header"><h2 id={titleId}>Ảnh chân dung {name}</h2><button type="button" className="icon-button" aria-label="Đóng ảnh chân dung" onClick={() => dialog.current?.close()}><X size={21}/></button></header>
      <div className="portrait-toolbar" role="group" aria-label="Điều chỉnh kích thước ảnh">
        <button type="button" className="btn compact" aria-label="Thu nhỏ ảnh" disabled={zoom <= 1} onClick={() => setZoom(value => Math.max(1, value - .5))}><Minus size={17}/></button>
        <span className="small" role="status" aria-live="polite">{zoom * 100}%</span>
        <button type="button" className="btn compact" aria-label="Phóng to ảnh" disabled={zoom >= 3} onClick={() => setZoom(value => Math.min(3, value + .5))}><Plus size={17}/></button>
        <button type="button" className="btn compact" aria-label="Đặt lại kích thước ảnh" disabled={zoom === 1} onClick={() => setZoom(1)}><RotateCcw size={15}/><span>Đặt lại</span></button>
      </div>
      <div className="portrait-stage" tabIndex={0} role="region" aria-label="Ảnh phóng to; cuộn để xem khi zoom">
        {open && <div className="portrait-canvas" style={{width: `${zoom * 100}%`, height: `${zoom * 100}%`}}><img src={source} alt={`Ảnh phóng to của ${name}`} onError={() => setFailed(true)}/></div>}
      </div>
      <p className="portrait-dialog-caption">Cuộn để xem ảnh khi phóng to. Nhấn Esc để đóng.</p>
    </dialog>
  </>;
  /* eslint-enable @next/next/no-img-element */
}
