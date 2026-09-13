const STEPS = ['warn1', 'warn2', 'bw_flag', 'p5s', 'p10s']
const LABEL = { warn1: 'W1', warn2: 'W2', bw_flag: 'B/W', p5s: '+5s', p10s: '+10s' }

export default function Ledger({ ledger }) {
  return (
    <div>
      <h1 className="screen-title">Penalty ledger</h1>
      <p className="screen-sub">
        Approved strikes drive the sporting-code escalation automatically:
        two warnings, black-and-white flag, then time penalties. Deterministic, auditable, profile-configurable.
      </p>
      {ledger.length === 0 && <div className="empty">No strikes yet. Approvals in the review queue land here.</div>}
      {ledger.map(e => (
        <div key={e.car_id ?? Math.random()} className="ledger-row">
          <span className="car">Car {e.car_id ?? '?'}</span>
          <div className="strike-track">
            {STEPS.map((s, i) => (
              <span key={s} className={`strike ${i < 2 ? 'warn' : ''} ${i < e.count ? 'hit' : ''}`}>{LABEL[s]}</span>
            ))}
          </div>
          <span className="next-alert">
            {e.next_step === 'p5s' || e.next_step === 'bw_flag'
              ? `next violation → ${LABEL[e.next_step]}` : `${e.count} strike${e.count === 1 ? '' : 's'}`}
          </span>
        </div>
      ))}
    </div>
  )
}
