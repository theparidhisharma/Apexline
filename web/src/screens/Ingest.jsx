import { useEffect, useRef, useState } from 'react'
import * as api from '../api/client.js'

export default function Ingest({ live, incidentCount, jobEvents = [], onDone }) {
  const [file, setFile] = useState(null)
  const [hot, setHot] = useState(false)
  const [busy, setBusy] = useState(false)
  const [engine, setEngine] = useState('geometry')
  const [calibs, setCalibs] = useState([])
  const [calib, setCalib] = useState('')
  const [model, setModel] = useState(null)
  const [localLog, setLocalLog] = useState([])
  const inputRef = useRef()

  useEffect(() => {
    api.getModel().then(setModel).catch(() => {})
    api.getCalibrations().then(cs => {
      setCalibs(cs)
      const pref = cs.find(c => c.name === 'corner_broadcast.json') || cs[0]
      if (pref) setCalib(pref.name)
    }).catch(() => {})
  }, [])

  const progress = [...jobEvents].reverse().find(e => e.type === 'progress')
  const done = [...jobEvents].reverse().find(e => e.type === 'job_done')
  const err = [...jobEvents].reverse().find(e => e.type === 'job_error')
  useEffect(() => { if (done || err) setBusy(false) }, [done, err])

  const push = t => setLocalLog(l => [...l, { t: new Date().toLocaleTimeString(), text: t }])

  async function start() {
    if (!file || busy) return
    setBusy(true)
    push(`uploading ${file.name} (${(file.size / 1e6).toFixed(1)} MB)…`)
    try {
      await api.bootstrap()
      await api.ingest(file, engine === 'geometry' ? calib : null, engine)
      push(engine === 'geometry'
        ? `processing (geometry) with ${calib} — watch progress below`
        : 'processing (Groq Vision) — frames are being scored by the VLM')
    } catch (e) {
      push(`ERROR: ${e.message}`)
      setBusy(false)
    }
  }

  return (
    <div>
      <h1 className="screen-title">Ingest session video</h1>
      <p className="screen-sub">
        Fixed camera, one corner in frame, boundary visible. Two engines:
        <b> Geometry</b> (needs a calibration for THIS camera view, pays back
        ±cm measurements) or <b>Groq Vision</b> (no calibration, works on any
        footage, frame-level judgement — no metric claims, routed to human
        review). Either way the output is the same: a cropped evidence clip
        per violation, taxonomy, confidence band, human-in-loop.
      </p>

      <div className="ingest-grid">
        <div>
          <div
            className={`drop ${hot ? 'hot' : ''} ${busy ? 'busy' : ''}`}
            onClick={() => inputRef.current.click()}
            onDragOver={e => { e.preventDefault(); setHot(true) }}
            onDragLeave={() => setHot(false)}
            onDrop={e => { e.preventDefault(); setHot(false); e.dataTransfer.files[0] && setFile(e.dataTransfer.files[0]) }}
          >
            {file
              ? <><b>{file.name}</b><br />{(file.size / 1e6).toFixed(1)} MB — ready</>
              : <><b>Drop video here</b> or click to browse<br />
                  demo clip ships at data/clips_src/broadcast.mp4</>}
            <input ref={inputRef} type="file" accept="video/*" hidden
                   onChange={e => e.target.files[0] && setFile(e.target.files[0])} />
          </div>

          <div className="engine-row">
            <label className={`engine ${engine === 'geometry' ? 'sel' : ''}`}>
              <input type="radio" checked={engine === 'geometry'} onChange={() => setEngine('geometry')} />
              <b>Geometry</b><span>calibrated · ±cm · offline</span>
            </label>
            <label className={`engine ${engine === 'vlm_groq' ? 'sel' : ''}`}>
              <input type="radio" checked={engine === 'vlm_groq'} onChange={() => setEngine('vlm_groq')} />
              <b>Groq Vision</b><span>any footage · no calibration · needs API key</span>
            </label>
          </div>

          {engine === 'geometry' && (
            <div className="calib-pick">
              <span>Calibration for this camera view:</span>
              <select value={calib} onChange={e => setCalib(e.target.value)}>
                {calibs.map(c => (
                  <option key={c.name} value={c.name}>
                    {c.name}{c.residual_px != null ? ` · resid ${c.residual_px}px` : ''}
                  </option>
                ))}
              </select>
              <em>Uploading your own footage? Calibrate THIS view first (Calibrate tab)
                  or the boundary will be in the wrong place and nothing will flag.</em>
            </div>
          )}

          <div className="cta-row" style={{ marginTop: 18 }}>
            <button className="cta" disabled={!file || busy || !live} style={{ opacity: !file || busy || !live ? 0.5 : 1 }}
                    onClick={start}>{busy ? 'Processing…' : 'Start processing ▸'}</button>
            {incidentCount > 0 && (
              <button className="cta ghost" onClick={onDone}>Open review queue ({incidentCount}) ▸</button>
            )}
          </div>
        </div>

        <div>
          <div className="job-log">
            <div className={live ? 'ok' : 'warn'}>
              backend: {live ? 'connected' : 'NOT REACHABLE — start it: uvicorn server.main:app --port 8000'}</div>
            {model && <div className="ok">model: {model.weights} {model.fine_tuned ? '(your fine-tune ✓)' : '(zero-shot COCO)'}</div>}
            {localLog.map((l, i) => <div key={i}>[{l.t}] {l.text}</div>)}
            {busy && progress && (
              <>
                <div className="progress-line">
                  <i style={{ width: `${progress.pct}%` }} />
                </div>
                <div>{progress.pct}% · frame {progress.frames_done}/{progress.total} ·
                  {' '}{progress.detections} car detections · {progress.incidents} incident(s)</div>
              </>
            )}
            {done && (
              <div className={done.incidents > 0 ? 'ok' : 'warn'}>
                DONE — {done.incidents} incident(s), {done.detections} detections.
                {done.hint && <div className="warn">⚠ {done.hint}</div>}
              </div>
            )}
            {err && <div className="warn">FAILED — {err.error}</div>}
          </div>
        </div>
      </div>
    </div>
  )
}
