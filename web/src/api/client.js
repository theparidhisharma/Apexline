// API client with fixture fallback: the console renders (and can be demoed)
// even if the backend is down — banner shows "fixtures" so nobody is misled.
const BASE = '/api'
export const SESSION_ID = 1

export const FIXTURES = {
  incidents: [
    { id: 412, track_id: 27, car: '27', type_code: 'V2', context_tags: [], t_start_ms: 1834200, duration_ms: 480,
      max_overshoot_m: 0.31, error_band_m: 0.06, confidence: 0.94, band: 'auto_flag', status: 'pending',
      advantage_gained_s: 0.21, clip_url: null,
      explain: { frames_fully_outside: 6, homography_residual_px: 1.8, cross_modal_agreement: 0.91, footprint_method: 'seg_mask' } },
    { id: 413, track_id: 14, car: '14', type_code: 'V2', context_tags: ['proximity'], t_start_ms: 2101000, duration_ms: 260,
      max_overshoot_m: 0.07, error_band_m: 0.09, confidence: 0.51, band: 'needs_review', status: 'pending',
      advantage_gained_s: null, clip_url: null,
      explain: { frames_fully_outside: 3, homography_residual_px: 1.8, cross_modal_agreement: 0.44, footprint_method: 'bbox_bottom', note: 'overshoot within error band — human call' } },
    { id: 414, track_id: 5, car: '5', type_code: 'V1', context_tags: [], t_start_ms: 903000, duration_ms: 120,
      max_overshoot_m: 0.02, error_band_m: 0.05, confidence: 0.22, band: 'auto_clear', status: 'pending',
      advantage_gained_s: null, clip_url: null,
      explain: { frames_fully_outside: 1, homography_residual_px: 1.8, footprint_method: 'bbox_bottom' } },
    { id: 415, track_id: 63, car: '63', type_code: 'V3', context_tags: ['position-changed'], t_start_ms: 2410000, duration_ms: 640,
      max_overshoot_m: 0.55, error_band_m: 0.07, confidence: 0.88, band: 'needs_review', status: 'pending',
      advantage_gained_s: 0.34, clip_url: null,
      explain: { frames_fully_outside: 8, homography_residual_px: 1.8, cross_modal_agreement: 0.87, footprint_method: 'seg_mask', note: 'V3 never auto-decides' } },
  ],
  ledger: [{ car_id: 27, count: 2, current_step: 'warn2', next_step: 'bw_flag',
             history: [{ step: 'warn1', incident_id: 401 }, { step: 'warn2', incident_id: 412 }] }],
  learning: {
    bands: { auto_clear: 0.33, auto_flag: 0.79 },
    defaults: { auto_clear: 0.35, auto_flag: 0.75 },
    n_decisions: 14,
    per_band: { auto_flag: { n: 8, approved: 7, rejected: 1, precision: 0.875 },
                needs_review: { n: 5, approved: 3, rejected: 2, precision: 0.6 },
                auto_clear: { n: 1, approved: 0, rejected: 1, precision: 0 } },
    history: [
      { band: 'auto_flag', to: 0.79, why: '1/8 auto-flags rejected (fp 13%)' },
      { band: 'auto_clear', to: 0.33, why: '1 approved violation within 0.10 of the clear line' },
    ],
    updated_at: 'fixtures',
  },
  predictions: [
    { car: '27', kind: 'pre_corner_prob', value: 0.78, detail: 'T4 entry +11 km/h over compliant envelope', model_version: 'f1-gbm-0.1' },
    { car: '44', kind: 'pre_corner_prob', value: 0.41, detail: 'T9 margin trend −4 cm/lap', model_version: 'f1-gbm-0.1' },
    { car: '27', kind: 'strike_risk', value: 0.83, detail: 'projected margin ≤ 0 within 3 laps at T4', model_version: 'f2-lin-0.1' },
    { car: '81', kind: 'strike_risk', value: 0.22, detail: 'stable margins', model_version: 'f2-lin-0.1' },
  ],
}

async function req(path, opts) {
  const r = await fetch(BASE + path, opts)
  if (!r.ok) throw new Error((await r.text()) || r.statusText)
  return r.json()
}

export async function getIncidents() { return req(`/sessions/${SESSION_ID}/incidents`) }
export async function decide(id, decision, note, penalty_step = null) {
  return req(`/incidents/${id}/decision`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ decision, note, penalty_step }),
  })
}
export async function bootstrap() { return req('/bootstrap', { method: 'POST' }) }
export async function getModel() { return req('/model') }
export async function getLearning() { return req('/learn/state') }
export async function ingest(file, calibration, engine = 'geometry') {
  const fd = new FormData()
  fd.append('file', file)
  const ps = new URLSearchParams({ engine })
  if (calibration) ps.set('calibration', calibration)
  return req(`/sessions/${SESSION_ID}/ingest?${ps}`, { method: 'POST', body: fd })
}
export async function getCalibrations() { return req('/calibrations') }
export async function getSessionStatus() { return req(`/sessions/${SESSION_ID}`) }
export async function getLedger() { return req(`/sessions/${SESSION_ID}/ledger`) }
export async function getPredictions() { return req(`/sessions/${SESSION_ID}/predictions`) }
export async function saveCalibration(cornerId, body) {
  return req(`/corners/${cornerId}/calibration`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
  })
}
export function openLive(onMessage) {
  try {
    const ws = new WebSocket(`${location.origin.replace('http', 'ws')}/api/sessions/${SESSION_ID}/live`)
    ws.onmessage = e => onMessage(JSON.parse(e.data))
    return ws
  } catch { return null }
}
