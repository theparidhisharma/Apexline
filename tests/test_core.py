import sys; sys.path.insert(0, '.')
import numpy as np
from pipeline.see.fsm import ViolationFSM
from pipeline.see.footprint import innermost_signed_distance
from pipeline.know.confidence import score, band
from pipeline.know.taxonomy import Context, classify
from pipeline.know.ledger import DriverLedger
from pipeline.physics import interpolation_bound, is_plausible_step

boundary = np.array([[0.0, 0.0], [10.0, 0.0], [20.0, 0.0]])  # track is y>0 side

def test_signed_distance():
    assert innermost_signed_distance(np.array([[5.0, 1.0]]), boundary) > 0   # inside
    assert innermost_signed_distance(np.array([[5.0, -0.5]]), boundary) < 0  # out
    # tyre-on-line case: one point out, one in -> innermost is inside -> legal
    assert innermost_signed_distance(np.array([[5.0, -0.3], [5.2, 0.05]]), boundary) > 0

def test_fsm_flicker_no_incident():
    fsm = ViolationFSM(k_out=3, m_in=2, dt_s=0.1)
    seq = [0.5, -0.1, 0.5, -0.1, 0.5, -0.1]  # flicker never sustains
    out = [fsm.step(1, i*100, d, (i*5.0, d), 0.05) for i, d in enumerate(seq)]
    assert all(o is None for o in out)

def test_fsm_clean_crossing_one_incident():
    fsm = ViolationFSM(k_out=3, m_in=2, dt_s=0.1)
    seq = [0.5, -0.2, -0.3, -0.4, -0.35, 0.2, 0.3, 0.4]
    incs = [fsm.step(1, i*100, d, (i*5.0, min(d,0)*0), 0.05) for i, d in enumerate(seq)]
    incs = [i for i in incs if i]
    assert len(incs) == 1 and abs(incs[0].max_overshoot_m - 0.4) < 1e-9

def test_7g_gate():
    dt = 0.1
    assert is_plausible_step((0,0), (5,0), (10,0), dt)          # constant velocity
    assert not is_plausible_step((0,0), (5,0), (30,0), dt)      # teleport: a=2000 m/s^2

def test_confidence_bands():
    c = score(0.31, 0.06, 1.0, 0.0, 1.8, 0.9)
    assert band(c) == 'auto_flag' and c > 0.75
    assert band(0.9, occlusion_ratio=0.5) == 'needs_review'     # occluded never auto-flags
    assert band(0.9, context_tags=['proximity']) == 'needs_review'

def test_taxonomy():
    assert classify(Context(session_type='quali'))[0] == 'V1'
    code, tags, auto = classify(Context(session_type='race')); assert code=='V2' and auto
    code, tags, auto = classify(Context(position_changed=True)); assert code=='V3' and not auto
    code, tags, auto = classify(Context(position_changed=True, gave_place_back=True)); assert code=='X'

def test_ledger_escalation():
    l = DriverLedger()
    steps = [l.apply_strike(i)['step'] for i in range(6)]
    assert steps == ['warn1','warn2','bw_flag','p5s','p10s','p10s']

def test_interp_bound():
    assert abs(interpolation_bound() - 0.547) < 0.01

def test_fsm_survives_detection_gap():
    """A missed frame used to deadlock the plausibility gate (stale history
    rejected every later sample). Real-timestamp gate + sliding history."""
    from pipeline.see.fsm import ViolationFSM
    fsm = ViolationFSM(k_out=3, m_in=2, dt_s=0.12)
    t, out, x = 0, [], 0.0
    seq = [0.2, 0.1, -0.2, None, -0.6, -0.8, -0.6, -0.2, 0.1, 0.2, 0.3]
    for d in seq:
        t += 120
        x += 1.4                      # ~11.6 m/s forward motion
        if d is None:                 # detection gap: no step at all
            continue
        out.append(fsm.step(1, t, d, (x, d), 0.05))
    cands = [c for c in out if c]
    assert len(cands) == 1, f"expected 1 incident despite the gap, got {len(cands)}"
    assert abs(cands[0].max_overshoot_m - 0.8) < 1e-6


for name, fn in list(globals().items()):
    if name.startswith('test_'):
        fn(); print(f'PASS {name}')
