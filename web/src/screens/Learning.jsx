import { useEffect, useState } from 'react'
import * as api from '../api/client.js'

export default function Learning() {
  const [st, setSt] = useState(null)
  useEffect(() => {
    api.getLearning().then(setSt).catch(() => setSt(api.FIXTURES.learning))
  }, [])
  if (!st) return null
  const b = st.bands || {}, d = st.defaults || { auto_clear: 0.35, auto_flag: 0.75 }
  const pb = st.per_band || {}

  return (
    <div>
      <h1 className="screen-title">Self-improvement loop</h1>
      <p className="screen-sub">
        Every steward verdict is ground truth. Rejected auto-flags push the flag
        threshold up; confirmed streaks relax it; violations approved near the
        clear line pull that line down. Adjustments are bounded, deterministic,
        and audited — the scoring formula never changes, only where the triage
        lines sit. Decisions also export as labelled hard examples for the next
        model fine-tune.
      </p>

      <div className="thresh-viz">
        <div className="mark ghost" style={{ left: `${d.auto_clear * 100}%` }}><i>{d.auto_clear} dflt</i></div>
        <div className="mark ghost" style={{ left: `${d.auto_flag * 100}%` }}><i>{d.auto_flag} dflt</i></div>
        <div className="mark" style={{ left: `${(b.auto_clear ?? d.auto_clear) * 100}%` }}><i>clear {b.auto_clear ?? d.auto_clear}</i></div>
        <div className="mark" style={{ left: `${(b.auto_flag ?? d.auto_flag) * 100}%` }}><i>flag {b.auto_flag ?? d.auto_flag}</i></div>
      </div>

      <div className="learn-grid">
        <div className="learn-card"><div className="k">Steward decisions ingested</div>
          <div className="v">{st.n_decisions ?? 0}</div></div>
        <div className="learn-card"><div className="k">Auto-flag precision</div>
          <div className="v">{pb.auto_flag?.precision != null ? `${(pb.auto_flag.precision * 100).toFixed(0)}%` : '—'}
            <small> {pb.auto_flag ? `${pb.auto_flag.approved}✓ / ${pb.auto_flag.rejected}✗` : 'no data yet'}</small></div></div>
        <div className="learn-card"><div className="k">Needs-review outcomes</div>
          <div className="v">{pb.needs_review?.n ?? 0}<small> human calls captured</small></div></div>
        <div className="learn-card"><div className="k">Fine-tune labels exported</div>
          <div className="v">{st.n_decisions ?? 0}<small> data/learned/review_labels.csv</small></div></div>
      </div>

      <div className="hist">
        <b style={{ color: 'var(--text)' }}>Recalibration history (audited)</b>
        {(st.history || []).length === 0 && <div>no adjustments yet — thresholds at defaults</div>}
        {(st.history || []).map((h, i) => (
          <div key={i}>▸ {h.band} → {h.to} — {h.why}</div>
        ))}
        {st.updated_at && <div style={{ marginTop: 8 }}>last update {st.updated_at}</div>}
      </div>
    </div>
  )
}
