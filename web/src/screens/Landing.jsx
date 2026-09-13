import { useEffect, useRef, useState } from 'react'

/* Animated race-control landing: live replay canvas (cars lapping a circuit,
   periodic track-limits event at T4 with red flash + steward chip), race
   control ticker, count-up stats, and an optional real video layer served by
   the backend (/api/media/broadcast.mp4) behind the hero. Fully offline. */

const TICKER = [
  'CAR 27 · TRACK LIMITS · TURN 4 — LAP TIME DELETED',
  'FIA-STYLE TRIAGE: 80% AUTO-CLEARED · HUMANS DECIDE THE REST',
  'CAR 81 · TRACK LIMITS · TURN 4 — WARNING (2/3)',
  'VISION VERIFIES AT ±2 CM · TELEMETRY PROPOSES AT ±0.55 M',
  'CAR 16 · OFF-TRACK · NO ADVANTAGE GAINED — NO FURTHER ACTION',
  'EVERY EVIDENCE CLIP SHA-256 SEALED · PROTEST-GRADE',
]

function useCountUp(target, ms = 1400) {
  const [v, setV] = useState(0)
  useEffect(() => {
    let raf, t0
    const tick = t => {
      if (!t0) t0 = t
      const p = Math.min((t - t0) / ms, 1)
      setV(target * (1 - Math.pow(1 - p, 3)))
      if (p < 1) raf = requestAnimationFrame(tick)
    }
    raf = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf)
  }, [target, ms])
  return v
}

function ReplayCanvas() {
  const ref = useRef()
  const flash = useRef({ until: 0, car: 27 })
  useEffect(() => {
    const cv = ref.current, ctx = cv.getContext('2d')
    let raf
    const DPR = Math.min(devicePixelRatio || 1, 2)
    const fit = () => {
      cv.width = cv.clientWidth * DPR
      cv.height = cv.clientHeight * DPR
    }
    fit()
    addEventListener('resize', fit)
    // stadium circuit centreline as parametric path
    const P = t => {
      const w = cv.width, h = cv.height
      const rx = w * 0.36, ry = h * 0.30, cx = w / 2, cy = h / 2
      const a = t * 2 * Math.PI
      // squircle-ish for straights
      const px = cx + rx * Math.sign(Math.cos(a)) * Math.pow(Math.abs(Math.cos(a)), 0.7)
      const py = cy + ry * Math.sign(Math.sin(a)) * Math.pow(Math.abs(Math.sin(a)), 0.7)
      return [px, py]
    }
    const cars = [
      { t: 0.00, v: 0.00116, col: '#e10600', n: 27 },
      { t: 0.38, v: 0.00109, col: '#00d2be', n: 44 },
      { t: 0.71, v: 0.00112, col: '#ffd800', n: 81 },
    ]
    const T4 = 0.125 // corner apex parameter (top-right)
    const draw = now => {
      const w = cv.width, h = cv.height
      ctx.clearRect(0, 0, w, h)
      // tarmac ribbon
      ctx.lineCap = 'round'
      ctx.strokeStyle = '#20202b'
      ctx.lineWidth = 34 * DPR
      ctx.beginPath()
      for (let i = 0; i <= 200; i++) {
        const [x, y] = P(i / 200)
        i ? ctx.lineTo(x, y) : ctx.moveTo(x, y)
      }
      ctx.closePath(); ctx.stroke()
      // white track-limit edge
      ctx.strokeStyle = 'rgba(245,245,245,.85)'
      ctx.lineWidth = 2 * DPR
      ctx.setLineDash([10 * DPR, 0])
      ctx.stroke()
      // T4 kerb + label
      const [tx, ty] = P(T4)
      ctx.fillStyle = '#e10600'
      ctx.font = `800 italic ${12 * DPR}px system-ui`
      ctx.fillText('T4', tx + 26 * DPR, ty - 10 * DPR)
      // violation flash zone
      const hot = now < flash.current.until
      if (hot) {
        ctx.beginPath()
        ctx.arc(tx, ty, 26 * DPR * (1 + 0.2 * Math.sin(now / 60)), 0, 7)
        ctx.strokeStyle = 'rgba(225,6,0,.8)'
        ctx.lineWidth = 3 * DPR
        ctx.stroke()
      }
      // cars + trails
      for (const c of cars) {
        c.t = (c.t + c.v) % 1
        for (let k = 8; k > 0; k--) {
          const [x, y] = P((c.t - k * 0.006 + 1) % 1)
          ctx.beginPath()
          ctx.arc(x, y, (7 - k * 0.6) * DPR, 0, 7)
          ctx.fillStyle = c.col + Math.floor(20 - k * 2).toString(16).padStart(2, '0')
          ctx.fill()
        }
        // car 27 runs wide at T4 every few laps
        let [x, y] = P(c.t)
        const nearT4 = Math.abs(c.t - T4) < 0.02
        if (c.n === 27 && nearT4 && Math.floor(performance.now() / 9000) % 2 === 0) {
          const push = (0.02 - Math.abs(c.t - T4)) / 0.02
          x += push * 24 * DPR; y -= push * 16 * DPR
          if (push > 0.85 && now > flash.current.until) flash.current.until = now + 2200
        }
        ctx.beginPath(); ctx.arc(x, y, 7 * DPR, 0, 7)
        ctx.fillStyle = c.col; ctx.fill()
        ctx.fillStyle = '#fff'
        ctx.font = `700 ${9 * DPR}px system-ui`
        ctx.fillText(c.n, x - 7 * DPR, y - 11 * DPR)
      }
      // steward chip when hot
      if (hot) {
        const msg = 'TRACK LIMITS · CAR 27 · T4'
        ctx.font = `800 italic ${13 * DPR}px system-ui`
        const tw = ctx.measureText(msg).width
        ctx.fillStyle = 'rgba(21,21,30,.92)'
        ctx.fillRect(tx - tw / 2 - 12 * DPR, ty - 62 * DPR, tw + 24 * DPR, 30 * DPR)
        ctx.fillStyle = '#e10600'
        ctx.fillRect(tx - tw / 2 - 12 * DPR, ty - 62 * DPR, 4 * DPR, 30 * DPR)
        ctx.fillStyle = '#fff'
        ctx.fillText(msg, tx - tw / 2, ty - 42 * DPR)
      }
      raf = requestAnimationFrame(draw)
    }
    raf = requestAnimationFrame(draw)
    return () => { cancelAnimationFrame(raf); removeEventListener('resize', fit) }
  }, [])
  return <canvas ref={ref} className="replay-canvas" />
}

function Stat({ value, decimals = 0, prefix = '', suffix = '', label }) {
  const v = useCountUp(value)
  return (
    <div className="stat">
      <div className="v">{prefix}<i>{v.toFixed(decimals)}</i>{suffix}</div>
      <div className="k">{label}</div>
    </div>
  )
}

export default function Landing({ onEnter }) {
  const [videoOk, setVideoOk] = useState(true)
  return (
    <div className="landing">
      <div className="topbar" />
      <div className="hero">
        {videoOk && (
          <video className="hero-video" src="/api/media/broadcast.mp4" autoPlay muted loop
                 playsInline onError={() => setVideoOk(false)} />
        )}
        <div className="hero-scrim" />
        <div className="hero-inner">
          <div className="kicker"><span className="live-dot" /> Race control · live triage · one camera</div>
          <h1>APEX<em>LINE</em></h1>
          <p className="strap">
            Below Formula 1, track limits are policed by eyeballs on monitors.
            APEXLINE puts <b>FIA-grade stewarding</b> on a single commodity camera:
            calibrated geometry detects, a deterministic rulebook classifies,
            evidence clips survive protests — and <b>humans make every call that matters</b>.
          </p>
          <div className="cta-row">
            <button className="cta" onClick={() => onEnter()}>Enter ops centre ▸</button>
            <button className="cta ghost" onClick={() => onEnter('ingest')}>Run a video demo</button>
          </div>
        </div>
      </div>

      <div className="ticker"><div className="ticker-track">
        {[...TICKER, ...TICKER].map((t, i) => <span key={i}>{t}<em>◆</em></span>)}
      </div></div>

      <div className="replay-panel">
        <div className="replay-head">
          <h2>Live replay · synthetic ground truth</h2>
          <p>Car 27 runs wide at Turn 4 every other lap. Watch race control catch it.</p>
        </div>
        <ReplayCanvas />
      </div>

      <div className="stat-strip">
        <Stat value={2} prefix="±" suffix=" cm" label="vision error band, distance-aware" />
        <Stat value={0.55} decimals={2} suffix=" m" label="telemetry ambiguity we refuse to judge on" />
        <Stat value={5} suffix=" min" label="corner calibration, stopwatch-timed" />
        <Stat value={7} prefix="V1–V" label="violation taxonomy, auto-mapped" />
        <Stat value={0} suffix=" LLM" label="in the decision path — by design" />
      </div>
      <div className="chequer" />
    </div>
  )
}
