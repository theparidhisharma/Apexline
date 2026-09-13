import { useEffect, useState } from 'react'
import * as api from './api/client.js'
import Landing from './screens/Landing.jsx'
import Ingest from './screens/Ingest.jsx'
import ReviewQueue from './screens/ReviewQueue.jsx'
import Ledger from './screens/Ledger.jsx'
import Calibrate from './screens/Calibrate.jsx'
import PitWall from './screens/PitWall.jsx'
import Learning from './screens/Learning.jsx'
import IncidentModal from './components/IncidentModal.jsx'

const SCREENS = [
  ['ingest', 'Ingest video'],
  ['queue', 'Review queue'],
  ['ledger', 'Penalty ledger'],
  ['learning', 'Learning loop'],
  ['pitwall', 'Pit wall'],
  ['calibrate', 'Calibrate'],
]

export default function App() {
  const [mode, setMode] = useState(location.hash === '#ops' ? 'ops' : 'landing')
  const [screen, setScreen] = useState('queue')
  const [incidents, setIncidents] = useState([])
  const [ledger, setLedger] = useState([])
  const [predictions, setPredictions] = useState([])
  const [live, setLive] = useState(false)
  const [model, setModel] = useState(null)
  const [open, setOpen] = useState(null)
  const [toast, setToast] = useState(null)
  const [jobEvents, setJobEvents] = useState([])
  const [newestId, setNewestId] = useState(null)

  async function load() {
    try {
      await api.bootstrap().catch(() => {})
      const [i, l, p] = await Promise.all([api.getIncidents(), api.getLedger(), api.getPredictions()])
      // live backend: show REAL data only — empty states are honest states
      setIncidents(i); setLedger(l); setPredictions(p)
      setLive(true)
      api.getModel().then(setModel).catch(() => {})
    } catch {
      setIncidents(api.FIXTURES.incidents)
      setLedger(api.FIXTURES.ledger)
      setPredictions(api.FIXTURES.predictions)
      setLive(false)
    }
  }

  useEffect(() => {
    load()
    const ws = api.openLive(msg => {
      if (msg.type === 'incident') {
        setIncidents(prev => [msg.payload, ...prev.filter(i => i.id !== msg.payload.id)])
        setNewestId(msg.payload.id)
        setTimeout(() => setNewestId(null), 4000)
        notify(`Incident — car ${msg.payload.car_id ?? msg.payload.track_id} · ${msg.payload.type_code} · ${msg.payload.band}`)
      }
      if (msg.type === 'ledger') {
        api.getLedger().then(setLedger).catch(() => {})
        notify(`Ledger: car ${msg.payload.car_id ?? '?'} → ${msg.payload.step}`)
      }
      if (msg.type === 'prediction') {
        setPredictions(prev => [{ ...msg.payload, live: true }, ...prev].slice(0, 40))
        notify(`FORESEE — car ${msg.payload.car}: ${Math.round(msg.payload.value * 100)}% violation risk, ${msg.payload.detail}`)
      }
      if (msg.type === 'learning') notify('Learning loop: thresholds recalibrated')
      if (msg.type === 'progress') {
        setJobEvents(prev => {
          const keep = prev.filter(e => e.type !== 'progress')
          return [...keep, { type: 'progress', ...msg.payload }].slice(-30)
        })
      }
      if (msg.type === 'job_done') {
        setJobEvents(prev => [...prev, { type: 'job_done', ...msg.payload }].slice(-30))
        notify(msg.payload.incidents > 0
          ? `Processing complete — ${msg.payload.incidents} incident(s) in the queue`
          : 'Processing complete — 0 incidents (see the job log for why)')
      }
      if (msg.type === 'job_error') {
        setJobEvents(prev => [...prev, { type: 'job_error', ...msg.payload }].slice(-30))
        notify(`Processing failed: ${msg.payload.error}`)
      }
    })
    return () => ws && ws.close()
  }, [])

  function notify(text) {
    setToast(text)
    setTimeout(() => setToast(null), 3500)
  }

  function enterOps(target) {
    setMode('ops')
    location.hash = '#ops'
    if (typeof target === 'string') setScreen(target)
  }

  async function decideIncident(id, decision, note, penalty) {
    try {
      const res = await api.decide(id, decision, note, penalty)
      setIncidents(prev => prev.map(i => (i.id === id ? res.incident : i)))
      if (res.ledger) { setLedger(await api.getLedger()); notify(`Car ${res.ledger.car_id ?? '?'}: ${res.ledger.step}`) }
      else if (res.learning) notify(`Verdict recorded — ${res.learning.n_decisions} decisions in the loop`)
    } catch {
      setIncidents(prev => prev.map(i => (i.id === id ? { ...i, status: decision, note } : i)))
      notify(decision === 'approved' ? 'Strike recorded (fixtures mode)' : 'Verdict recorded (fixtures mode)')
    }
    setOpen(null)
  }

  if (mode === 'landing') return <Landing onEnter={enterOps} />

  const prog = [...jobEvents].reverse().find(e => e.type === 'progress')
  const processing = prog && !prog.done

  return (
    <div className="shell">
      {processing && <div className="global-progress"><i style={{ width: `${prog.pct}%` }} /></div>}
      <nav className="rail">
        <div className="brand" style={{ cursor: 'pointer' }} onClick={() => { setMode('landing'); location.hash = '' }}>APEX<em>LINE</em></div>
        <div className="brand-sub">Race control · ops centre</div>
        <div className="boundary-rule" aria-hidden="true" />
        {SCREENS.map(([id, label]) => (
          <button key={id} className={screen === id ? 'active' : ''} onClick={() => setScreen(id)}>{label}</button>
        ))}
        <div className="spacer" />
        {model && <div className="model-chip">model<b>{model.fine_tuned ? 'fine-tuned ✓' : 'zero-shot'}</b></div>}
        <div className={`conn ${live ? '' : 'off'}`}>feed <b>{live ? 'live' : 'fixtures'}</b></div>
      </nav>
      <main className="main">
        {screen === 'ingest' && <Ingest live={live} incidentCount={incidents.length} jobEvents={jobEvents} onDone={() => setScreen('queue')} />}
        {screen === 'queue' && <ReviewQueue incidents={incidents} live={live} newestId={newestId} onOpen={setOpen} />}
        {screen === 'ledger' && <Ledger ledger={ledger} />}
        {screen === 'learning' && <Learning />}
        {screen === 'pitwall' && <PitWall predictions={predictions} />}
        {screen === 'calibrate' && <Calibrate />}
      </main>
      {open && <IncidentModal inc={open} onDecide={decideIncident} onClose={() => setOpen(null)} />}
      {toast && <div className="toast">{toast}</div>}
    </div>
  )
}
