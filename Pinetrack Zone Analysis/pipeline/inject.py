"""Synthetic-defect injection test: add a realistic car-body response to a track impact/dip at a chosen chainage
into the RAW accelerometer stream of every eastbound recording, re-run features + detection, and check recovery."""
import numpy as np, pandas as pd
from features2 import frame_features, bin_frames, FEATS

def defect_waveform(fs=100.0, amp=1.0, rng=None):
    """Car-body vertical response to a short track irregularity: 1.6 Hz bounce + 9-12 Hz flex mode, decaying."""
    t = np.arange(0, 3.0, 1 / fs)
    f2 = rng.uniform(8, 13)
    w = 0.35 * np.sin(2 * np.pi * 1.6 * t) * np.exp(-t / 0.8) + np.sin(2 * np.pi * f2 * t) * np.exp(-t / 0.25)
    return amp * w / np.abs(w).max()

def inject(sig, s0, amp, rng, jitter_m=6.0, amp_var=0.3):
    s = sig['s']; v = sig['v']
    target = s0 + rng.normal(0, jitter_m)
    i = np.argmin(np.abs(s - target))
    if abs(s[i] - target) > 10 or v[i] < 3: return None
    out = dict(sig); av = sig['av'].copy()
    a = amp * (1 + rng.normal(0, amp_var))
    # two bogies of the car: second hit one bogie spacing (~18 m) later
    for off_m in (0.0, 18.0):
        j = np.argmin(np.abs(s - (s[i] + off_m * np.sign(s[-1] - s[0]))))
        wf = defect_waveform(amp=a, rng=rng); n = min(len(wf), len(av) - j)
        av[j:j + n] += wf[:n]
    out['av'] = av
    return out, i

def local_frames(sig, i, half_s=12):
    n = len(sig['t']); a, b = max(0, i - int(half_s * 100)), min(n, i + int(half_s * 100))
    loc = {k: (val[a:b] if isinstance(val, np.ndarray) and len(val) == n else val) for k, val in sig.items()}
    return frame_features(loc)
