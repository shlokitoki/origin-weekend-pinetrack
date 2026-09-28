"""Track features after removing wheel-order and onboard-tone energy (STFT masking), in 5 m bins."""
import numpy as np, pandas as pd
from scipy.signal import stft
from signals import bp
from wheel import strip_mask

NPER, HOP, FSR = 128, 12, 100.0
BANDS = {'v_body': (0.7, 3.0), 'v_struct': (6.0, 20.0), 'v_high': (20.0, 45.0)}

def band_power(f, P, keep, lo, hi):
    inb = (f >= lo) & (f < hi)
    k = keep & inb[:, None]
    # mean PSD over kept bins x full bandwidth (robust to masked bins)
    return (P * k).sum(0) / np.maximum(k.sum(0), 1) * inb.sum()

def frame_features(sig, D=0.708):
    out = {}
    f, t, Z = stft(sig['av'], fs=FSR, nperseg=NPER, noverlap=NPER - HOP, boundary=None, padded=False)
    P = np.abs(Z)**2
    tt = sig['t'][0] + t
    v = np.interp(tt, sig['t'], sig['v'])
    keep = ~strip_mask(f, v, D)
    for k, (lo, hi) in BANDS.items():
        out[k] = np.sqrt(band_power(f, P, keep, lo, hi))
        out[k + '_raw'] = np.sqrt(band_power(f, P, np.ones_like(keep), lo, hi))
    # horizontal: total PSD of the 3 horizontal components (rotation-invariant), same masking
    Ph = 0
    for j in range(3):
        fh, _, Zh = stft(sig['ah'][:, j], fs=FSR, nperseg=NPER, noverlap=NPER - HOP, boundary=None, padded=False)
        Ph = Ph + np.abs(Zh)**2
    out['h_body'] = np.sqrt(band_power(fh, Ph, keep, 0.5, 3.0))
    out['h_struct'] = np.sqrt(band_power(fh, Ph, keep, 6.0, 20.0))
    rot = np.linalg.norm(bp(sig['wh'], 0.3, 5.0), axis=1)
    out['rot'] = np.sqrt(np.interp(tt, sig['t'], bp(rot**2, None, 1.0)).clip(0))
    # impulsiveness: kurtosis of 6-45 Hz vertical within frame (time domain)
    x = bp(sig['av'], 6.0, 45.0)
    idx = (np.arange(len(t))[:, None] * HOP + np.arange(NPER)[None]).clip(0, len(x) - 1)
    seg = x[idx]
    out['v_crest'] = np.abs(seg).max(1) / (seg.std(1) + 1e-9)
    out['v_peak'] = np.abs(seg).max(1)
    hand = np.interp(tt, sig['t'], sig['hand'].astype(float))
    oriented = np.interp(tt, sig['t'], (~np.isnan(sig['alat'])).astype(float))
    df = pd.DataFrame(out); df['t'] = tt; df['v'] = v; df['hand'] = hand; df['oriented'] = oriented
    df['s'] = np.interp(tt, sig['t'], sig['s'])
    return df

FEATS = ['v_body', 'v_struct', 'v_high', 'v_body_raw', 'v_struct_raw', 'h_body', 'h_struct', 'rot', 'v_crest', 'v_peak']

def bin_frames(df, sig, bin_m=5.0, vmin=3.0):
    d = df[df.v > vmin].copy()
    d['b'] = np.floor(d.s / bin_m).astype(int)
    agg = {k: 'mean' for k in FEATS}; agg.update(v_peak='max', v_crest='max', v='mean', hand='mean', oriented='mean')
    g = d.groupby('b').agg(agg); g['n'] = d.groupby('b').size()
    g['s'] = (g.index + 0.5) * bin_m
    g['name'] = sig['name']; g['trip'] = sig['trip']; g['dir'] = sig['dir']; g['phone'] = sig['phone']
    return g.reset_index()
