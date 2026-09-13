export default function PitWall({ predictions }) {
  const live = predictions.filter(p => p.live)
  const pre = predictions.filter(p => p.kind === 'pre_corner_prob' && !p.live)
  const risk = predictions.filter(p => p.kind === 'strike_risk')
  const cls = v => (v > 0.6 ? 'p-high' : v > 0.35 ? 'p-mid' : 'p-low')
  return (
    <div>
      <h1 className="screen-title">Pit wall — FORESEE</h1>
      <p className="screen-sub">
        Warnings before the strike, not after the stewards’ notification. Gradient-boosted models on
        structured telemetry — every score carries its model version and feature importances are one click away.
      </p>
      {live.length > 0 && (
        <div className="pw-panel pw-live">
          <h3><span className="live-dot" /> Live — violation risk before the crossing</h3>
          {live.map((p, i) => (
            <div key={p.id ?? i} className="pred pred-live">
              <span>Car {p.car} · {p.detail} · slope {p.features?.slope_m_s} m/s</span>
              <span className="p-high">{Math.round(p.value * 100)}%</span>
            </div>
          ))}
        </div>
      )}
      <div className="pw-grid">
        <div className="pw-panel">
          <h3>Pre-corner violation probability (F-1)</h3>
          {pre.length === 0 && <div className="empty">Import telemetry to see live probabilities.</div>}
          {pre.map((p, i) => (
            <div key={i} className="pred">
              <span>Car {p.car ?? p.car_id} — {p.detail || p.model_version}</span>
              <span className={cls(p.value)}>{Math.round(p.value * 100)}%</span>
            </div>
          ))}
        </div>
        <div className="pw-panel">
          <h3>Strike-risk horizon (F-2, next 3 laps)</h3>
          {risk.length === 0 && <div className="empty">Needs ≥4 laps of margin history per driver.</div>}
          {risk.map((p, i) => (
            <div key={i} className="pred">
              <span>Car {p.car ?? p.car_id} — {p.detail || p.model_version}</span>
              <span className={cls(p.value)}>{Math.round(p.value * 100)}%</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
