import { useEffect, useRef, useState } from 'react'
import { saveCalibration } from '../api/client.js'

// The five-minute installation. Two modes:
//  1. Reference points (≥4 clicks with known world spacing) → homography
//  2. Boundary trace (polyline along the operative limit)
export default function Calibrate() {
  const canvasRef = useRef()
  const [img, setImg] = useState(null)
  const [mode, setMode] = useState('points')
  const [points, setPoints] = useState([])       // [{u,v}]
  const [boundary, setBoundary] = useState([])   // [{u,v}]
  const [worldText, setWorldText] = useState('0,0\n5,0\n5,5\n0,5')
  const [reference, setReference] = useState('white_line')
  const [result, setResult] = useState(null)
  const [err, setErr] = useState(null)
  const [t0] = useState(Date.now())

  useEffect(() => {
    const c = canvasRef.current
    const ctx = c.getContext('2d')
    ctx.fillStyle = '#000'; ctx.fillRect(0, 0, c.width, c.height)
    if (img) ctx.drawImage(img, 0, 0, c.width, c.height)
    else {
      ctx.fillStyle = '#8b97a6'; ctx.font = '14px sans-serif'; ctx.textAlign = 'center'
      ctx.fillText('Load a corner still to calibrate (Choose file below)', c.width / 2, c.height / 2)
    }
    ctx.lineWidth = 2
    points.forEach((p, i) => {
      ctx.strokeStyle = '#57a6d9'; ctx.fillStyle = '#57a6d9'
      ctx.beginPath(); ctx.arc(p.u, p.v, 6, 0, Math.PI * 2); ctx.stroke()
      ctx.font = '12px monospace'; ctx.textAlign = 'left'; ctx.fillText(String(i + 1), p.u + 9, p.v - 9)
    })
    if (boundary.length) {
      ctx.strokeStyle = '#f2f4f7'; ctx.beginPath()
      boundary.forEach((p, i) => (i ? ctx.lineTo(p.u, p.v) : ctx.moveTo(p.u, p.v)))
      ctx.stroke()
    }
  }, [img, points, boundary])

  function onFile(e) {
    const f = e.target.files[0]
    if (!f) return
    const im = new Image()
    im.onload = () => setImg(im)
    im.src = URL.createObjectURL(f)
  }
  function onClick(e) {
    const r = canvasRef.current.getBoundingClientRect()
    const scale = canvasRef.current.width / r.width
    const p = { u: (e.clientX - r.left) * scale, v: (e.clientY - r.top) * scale }
    mode === 'points' ? setPoints([...points, p]) : setBoundary([...boundary, p])
  }
  async function confirm() {
    setErr(null)
    try {
      const world = worldText.trim().split('\n').map(l => l.split(',').map(Number))
      const res = await saveCalibration(1, {
        image_points: points.map(p => [p.u, p.v]),
        world_points: world,
        boundary: boundary.map(p => [p.u, p.v]),
        boundary_reference: reference,
      })
      setResult({ ...res, elapsed: Math.round((Date.now() - t0) / 1000) })
    } catch (e) { setErr(String(e.message || e)) }
  }

  return (
    <div>
      <h1 className="screen-title">Calibrate corner</h1>
      <p className="screen-sub">
        Click at least four ground reference points with known spacing, trace the operative boundary,
        pick what this corner’s limit actually is. That is the entire installation.
      </p>
      <div className="calib-grid">
        <div className="calib-canvas">
          <canvas ref={canvasRef} width={860} height={484} onClick={onClick} />
        </div>
        <div className="calib-panel">
          <h4>1 · Corner still</h4>
          <input type="file" accept="image/*" onChange={onFile} style={{ marginBottom: 12 }} />
          <h4>2 · Click mode</h4>
          <select value={mode} onChange={e => setMode(e.target.value)}>
            <option value="points">Reference points ({points.length} placed)</option>
            <option value="boundary">Boundary trace ({boundary.length} vertices)</option>
          </select>
          <h4>3 · World coordinates (m, one “x,y” per point)</h4>
          <textarea rows={4} value={worldText} onChange={e => setWorldText(e.target.value)} />
          <h4>4 · Boundary reference for this corner</h4>
          <select value={reference} onChange={e => setReference(e.target.value)}>
            <option value="white_line">White line (default track edge)</option>
            <option value="kerb_edge">Kerb edge (per race-director note)</option>
            <option value="custom">Custom polyline</option>
          </select>
          <button className="btn approve" style={{ width: '100%' }} onClick={confirm}
                  disabled={points.length < 4 || boundary.length < 2}>
            Confirm calibration
          </button>
          {result && (
            <p className={`residual ${result.residual_px > 3 ? 'bad' : ''}`}>
              Residual <b>{result.residual_px.toFixed(2)} px</b> · v{result.version} · {result.elapsed}s elapsed
              {result.residual_px > 3 && ' — re-place points; auto-actions stay frozen above 3 px'}
            </p>
          )}
          {err && <p className="residual bad"><b>{err}</b></p>}
          <button className="ghost-btn" onClick={() => { setPoints([]); setBoundary([]); setResult(null) }}>Start over</button>
        </div>
      </div>
    </div>
  )
}
