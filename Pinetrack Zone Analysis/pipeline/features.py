"""Distance-domain features: per recording, per 5 m bin of chainage."""
import numpy as np, pandas as pd
from signals import bp, FS

BIN = 5.0
BANDS = {  # name: (signal, lo, hi, stat)
    'v_body': ('av', 0.7, 3.0, 'rms'),     # car-body bounce/pitch -> long-wave vertical profile (dips, settlement)
    'v_struct': ('av', 6.0, 20.0, 'rms'),  # car-body flex band -> short-wave vertical (joints, crossings, frogs, squats)
    'v_peak': ('av', 6.0, 20.0, 'peak'),   # largest single jolt in the bin
    'h_body': ('hmag_lo', None, None, 'rms'),   # horizontal sway (lateral where oriented)
    'h_struct': ('hmag_hi', None, None, 'rms'),
    'rot': ('rot', None, None, 'rms'),     # roll+pitch rate 0.5-3 Hz -> twist / cross-level
}

def channels(sig):
    c = {'av': sig['av']}
    lat = sig['alat']; hasl = ~np.isnan(lat)
    hlo = np.linalg.norm(bp(sig['ah'], 0.5, 3.0), axis=1)
    lat_lo = bp(np.nan_to_num(lat), 0.5, 3.0)
    c['hmag_lo'] = np.where(hasl, np.abs(lat_lo), hlo)      # prefer true lateral
    c['hmag_hi'] = np.linalg.norm(bp(sig['ah'], 6.0, 20.0), axis=1)
    c['rot'] = np.linalg.norm(bp(sig['wh'], 0.5, 3.0), axis=1)
    return c

def bin_features(sig, bin_m=BIN, vmin=3.0):
    c = channels(sig)
    filt = {}
    for k, (src, lo, hi, stat) in BANDS.items():
        x = c[src]
        if lo is not None: x = bp(x, lo, hi)
        filt[k] = (np.abs(x), stat)
    s = sig['s']; v = sig['v']; hand = sig['hand']
    b = np.floor(s / bin_m).astype(int)
    df = pd.DataFrame({'b': b, 'v': v, 'hand': hand.astype(float)})
    for k, (x, stat) in filt.items():
        df[k] = x**2 if stat == 'rms' else x
    agg = {'v': 'mean', 'hand': 'mean'}
    agg.update({k: ('max' if BANDS[k][3] == 'peak' else 'mean') for k in BANDS})
    g = df[df.v > vmin].groupby('b').agg(agg)
    g['n'] = df[df.v > vmin].groupby('b').size()
    for k in BANDS:
        if BANDS[k][3] == 'rms': g[k] = np.sqrt(g[k])
    g['s'] = (g.index + 0.5) * bin_m
    g['name'] = sig['name']; g['trip'] = sig['trip']; g['dir'] = sig['dir']; g['phone'] = sig['phone']
    return g.reset_index()

def speed_normalize(df, feats=tuple(BANDS), min_n=5):
    """Per recording: log(feature) = f(log v) fitted by binned medians (captures phone placement +
    speed dependence). Residual z = (log x - f) / robust sd. Positive z = rougher than typical track at that speed."""
    out = []
    for name, d in df.groupby('name'):
        d = d.copy()
        ok = (d.hand < 0.3) & (d.n >= min_n)
        lv = np.log(d.v)
        edges = np.quantile(lv[ok], np.linspace(0, 1, 9))
        for k in feats:
            lx = np.log(d[k] + 1e-6)
            idx = np.clip(np.searchsorted(edges, lv) - 1, 0, 7)
            med = np.array([np.median(lx[ok & (idx == j)]) if (ok & (idx == j)).sum() > 5 else np.nan for j in range(8)])
            ctr = np.array([np.median(lv[ok & (idx == j)]) if (ok & (idx == j)).sum() > 5 else np.nan for j in range(8)])
            good = ~np.isnan(med)
            f = np.interp(lv, ctr[good], med[good])
            r = lx - f
            sd = 1.4826 * np.median(np.abs(r[ok] - np.median(r[ok])))
            d['z_' + k] = np.where(ok, r / sd, np.nan)
        out.append(d)
    return pd.concat(out, ignore_index=True)
