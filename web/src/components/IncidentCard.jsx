import ConfidenceBar from './ConfidenceBar.jsx'

export default function IncidentCard({ inc, onOpen, fresh }) {
  return (
    <button className={`card ${fresh ? "fresh" : ""}`} onClick={() => onOpen(inc)}>
      <div className="row1">
        <span className="car">Car {inc.car || inc.track_id}</span>
        <span className="type">{inc.type_code} · {fmtTime(inc.t_start_ms)}</span>
      </div>
      <div className="metrics">
        <span>out <b>{inc.max_overshoot_m != null ? (inc.max_overshoot_m * 100).toFixed(0) : '—'} cm</b> {inc.error_band_m != null ? ` ± ${(inc.error_band_m * 100).toFixed(0)}` : ''}</span>
        <span><b>{inc.duration_ms}</b> ms</span>
        {inc.advantage_gained_s != null && <span>gained <b>{inc.advantage_gained_s.toFixed(2)} s</b></span>}
      </div>
      {(inc.context_tags?.length > 0 || inc.status !== 'pending') && (
        <div className="tags">
          {inc.context_tags?.map(t => <span key={t} className="tag warn">{t}</span>)}
          {inc.status !== 'pending' && <span className={`status-chip status-${inc.status}`}>{inc.status}</span>}
        </div>
      )}
      <ConfidenceBar value={inc.confidence} />
    </button>
  )
}

export function fmtTime(ms) {
  const s = Math.floor(ms / 1000)
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`
}
