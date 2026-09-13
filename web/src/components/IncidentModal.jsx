import { useRef, useState } from 'react'
import { fmtTime } from './IncidentCard.jsx'

const TAXONOMY = {
  V1: 'Qualifying lap-time breach — lap deletion',
  V2: 'Race track-limits breach — strike accrues',
  V3: 'Overtake completed off-track — position review',
  V4: 'Advantage gained & kept — time review',
  V5: 'Forced off by another car — no fault',
  V6: 'Avoidance / evasive action — excusable',
  V7: 'Repeated systematic abuse — escalation',
  X:  'Exception — advantage surrendered',
}
const PENALTIES = [
  ['', 'Ledger decides (recommended)'],
  ['warn1', 'Warning 1'], ['warn2', 'Warning 2'],
  ['bw_flag', 'Black & white flag'], ['p5s', '+5 s penalty'], ['p10s', '+10 s penalty'],
]

export default function IncidentModal({ inc, onDecide, onClose }) {
  const noteRef = useRef()
  const videoRef = useRef()
  const [penalty, setPenalty] = useState('')
  const canDecide = inc.status === 'pending'
  const setRate = r => { if (videoRef.current) videoRef.current.playbackRate = r }
  const step = d => { if (videoRef.current) { videoRef.current.pause(); videoRef.current.currentTime += d } }

  const hitlRequired = inc.band === 'needs_review'
  const hitlClass = inc.band === 'auto_flag' ? 'auto' : inc.band === 'auto_clear' ? 'clear' : ''
  const hitlText = hitlRequired
    ? 'HUMAN IN LOOP — REQUIRED. Inside error band, occluded, or context-tagged: the system will not decide this. Your call is final and feeds the learning loop.'
    : inc.band === 'auto_flag'
      ? 'AUTO-FLAG — high confidence, clean geometry. One-click confirm; reject if wrong and the flag threshold recalibrates.'
      : 'AUTO-CLEARED — logged and queryable. Override available if the system missed something.'

  return (
    <div className="overlay" onClick={onClose}>
      <div className="modal" onClick={e => e.stopPropagation()}>
        <h2>
          <span className="mono">Car {inc.car || inc.track_id}</span>
          <span>{fmtTime(inc.t_start_ms)} · {inc.duration_ms} ms</span>
        </h2>

        {inc.clip_url
          ? <video ref={videoRef} src={inc.clip_url} controls autoPlay loop muted />
          : <div className="clip-missing">Evidence clip renders here after processing — cropped to the incident window, boundary + call burned in, SHA-256 sealed</div>}
        <div className="player-controls">
          <button onClick={() => setRate(0.25)}>0.25×</button>
          <button onClick={() => setRate(0.5)}>0.5×</button>
          <button onClick={() => setRate(1)}>1×</button>
          <button onClick={() => step(-1 / 25)}>◂ frame</button>
          <button onClick={() => step(1 / 25)}>frame ▸</button>
        </div>

        <div className="verdict-grid">
          <div className="verdict">
            <div className="k">Violation classification</div>
            <div className="v">{inc.type_code}<small>{TAXONOMY[inc.type_code] || 'unmapped'}</small></div>
          </div>
          <div className="verdict">
            <div className="k">Accuracy score (confidence)</div>
            <div className="v">{(inc.confidence * 100).toFixed(0)}%
              <small>band: {inc.band.replace('_', ' ')}
                {inc.error_band_m != null ? ` · ±${(inc.error_band_m * 100).toFixed(0)} cm at this range`
                  : ` · ${inc.explain?.engine === 'vlm_groq' ? 'Groq Vision judgement — no metric claim' : ''}`}</small></div>
          </div>
          {inc.explain?.predicted_lead_ms != null && (
            <div className="verdict foresee-hit">
              <div className="k">FORESEE — called before it happened</div>
              <div className="v">{inc.explain.predicted_lead_ms} ms early
                <small>pre-corner risk {(inc.explain.predicted_risk * 100).toFixed(0)}% while still inside the line</small></div>
            </div>
          )}
          <div className={`verdict hitl ${hitlClass}`}>
            <div className="k">Human-in-loop decision</div>
            <div style={{ fontSize: 13, lineHeight: 1.55, marginTop: 6 }}>{hitlText}</div>
          </div>
        </div>

        <h4 style={{ fontSize: 12, margin: '0 0 4px', letterSpacing: '.1em' }}>WHEELS BEYOND BOUNDARY</h4>
        <WheelTimeline frames={inc.explain?.frames_fully_outside ?? 4} />

        <div className="explain">
{inc.max_overshoot_m != null
  ? `peak overshoot     ${(inc.max_overshoot_m * 100).toFixed(0)} cm  (±${((inc.error_band_m ?? 0) * 100).toFixed(0)} cm)`
  : `engine             ${inc.explain?.engine || 'geometry'}  (${inc.explain?.model || ''})`}
{`
frames fully out   ${inc.explain?.frames_fully_outside ?? '—'}`}
{`
homography resid.  ${inc.explain?.homography_residual_px ?? '—'} px
cross-modal agree  ${inc.explain?.cross_modal_agreement ?? '—'}
footprint method   ${inc.explain?.footprint_method ?? '—'}`}
{inc.advantage_gained_s != null ? `\nadvantage gained   ${inc.advantage_gained_s.toFixed(2)} s vs compliant laps` : ''}
{inc.explain?.peak_world_m ? `\npeak world (m)     x ${inc.explain.peak_world_m[0]} · y ${inc.explain.peak_world_m[1]}  (corner frame)` : ''}
{inc.explain?.peak_bbox_px ? `\npeak bbox (px)     [${inc.explain.peak_bbox_px.join(', ')}]` : ''}
{inc.explain?.wheel_distances_m ? `\nwheel dists (m)    ${inc.explain.wheel_distances_m.join(' · ')}  (− = beyond line)` : ''}
{inc.explain?.note ? `\nnote               ${inc.explain.note}` : ''}
{inc.clip_sha256 ? `\nclip sha-256       ${inc.clip_sha256.slice(0, 16)}…` : ''}
        </div>

        {canDecide ? (
          <div className="decide">
            <input ref={noteRef} placeholder="Decision note (audit log)" />
            <select value={penalty} onChange={e => setPenalty(e.target.value)} title="Penalty">
              {PENALTIES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
            </select>
            <button className="btn approve" onClick={() => onDecide(inc.id, 'approved', noteRef.current.value, penalty || null)}>Approve violation</button>
            <button className="btn reject" onClick={() => onDecide(inc.id, 'rejected', noteRef.current.value, null)}>Mark wrong</button>
            <button className="btn escalate" onClick={() => onDecide(inc.id, 'escalated', noteRef.current.value, null)}>Escalate</button>
          </div>
        ) : (
          <p style={{ color: 'var(--text-dim)' }}>Decided: {inc.status}{inc.note ? ` — “${inc.note}”` : ''}. The verdict is in the learning loop; the record stays queryable.</p>
        )}
      </div>
    </div>
  )
}

function WheelTimeline({ frames }) {
  const total = Math.max(frames + 4, 10)
  return (
    <div className="wheel-timeline" aria-label="per-frame boundary state">
      {Array.from({ length: total }, (_, i) => {
        const out = i >= 2 && i < 2 + frames
        return <i key={i} style={{ background: out ? 'var(--flag)' : 'var(--clear)', opacity: out ? 1 : 0.45 }} />
      })}
    </div>
  )
}
