"""Apply the Beijing-trained, phone-compatible defect model to our E Line runs (20 m windows, 10 m hop)."""
import numpy as np, pandas as pd
from signals import bp

def windows20(sig, win=20.0, hop=10.0, vmin=4.0):
    v_ = bp(sig['av'], 0.5, 20.0)
    lat = np.where(np.isnan(sig['alat']), np.linalg.norm(bp(sig['ah'], 0.5, 20.0), axis=1), np.abs(bp(np.nan_to_num(sig['alat']), 0.5, 20.0)))
    rot = np.linalg.norm(bp(sig['wh'], 0.3, 5.0), axis=1)
    s = sig['s']; ok = (sig['v'] > vmin) & ~sig['hand']
    starts = np.arange(np.floor(s[ok].min() / hop) * hop, s[ok].max(), hop)
    order = np.argsort(s); ss = s[order]
    rows = []
    for a in starts:
        i0, i1 = np.searchsorted(ss, [a, a + win]); idx = order[i0:i1]; idx = idx[ok[idx]]
        if len(idx) < 20: continue
        rows.append(dict(s=a + win / 2, vel=sig['v'][idx].mean(), v_std=v_[idx].std(), v_max=np.abs(v_[idx]).max(),
                         lat_mean=lat[idx].mean(), lat_max=lat[idx].max(), rot_mean=rot[idx].mean(), rot_max=rot[idx].max()))
    d = pd.DataFrame(rows); d['name'] = sig['name']; d['trip'] = sig['trip']; d['dir'] = sig['dir']
    return d

def own_speed_z(d, feats, nb=8):
    """Same relative scaling as the Beijing SpeedNorm, but fitted within each recording."""
    out = []
    for name, g in d.groupby('name'):
        g = g.copy(); edges = np.quantile(g.vel, np.linspace(0, 1, nb + 1)); idx = np.clip(np.searchsorted(edges, g.vel) - 1, 0, nb - 1)
        for f in feats:
            lx = np.log(g[f] + 1e-6); z = np.full(len(g), np.nan)
            for j in range(nb):
                m = idx == j
                if m.sum() < 5: continue
                med = np.median(lx[m]); mad = 1.4826 * np.median(np.abs(lx[m] - med)); z[m] = (lx[m] - med) / mad
            g['z_' + f] = z
        out.append(g)
    return pd.concat(out, ignore_index=True)
