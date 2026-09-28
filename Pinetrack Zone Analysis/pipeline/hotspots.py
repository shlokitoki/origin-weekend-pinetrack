"""Repeatability-based hotspot detection: a location is flagged only if independent trains agree."""
import numpy as np, pandas as pd

COMPOSITE = ['z_v_high', 'z_v_peak', 'z_v_struct', 'z_v_body', 'z_h_struct', 'z_rot']
NB = 1930

def train_profiles(df, feats=COMPOSITE, smooth=4):
    df = df.copy(); df['comp'] = df[feats].mean(1)
    B = np.arange(NB); prof = {}
    for (trip, d), g in df.groupby(['trip', 'dir']):
        p = g.groupby('b')['comp'].median().reindex(B)
        prof[trip] = (d, p.rolling(smooth, center=True, min_periods=2).mean().values)
    return prof

def detect(prof, direction, n_perm=3000, seed=0, min_shift=100):
    rng = np.random.default_rng(seed)
    P = np.array([p for d, p in prof.values() if d == direction])      # trains x bins
    valid = ~np.isnan(P)
    M = np.nanmean(P, 0); cnt = valid.sum(0)
    # null: circularly shift each train's profile independently (breaks location alignment, keeps autocorrelation)
    null_max = np.empty(n_perm); null_all = []
    for k in range(n_perm):
        Q = np.array([np.roll(p, rng.integers(min_shift, NB - min_shift)) for p in P])
        m = np.nanmean(Q, 0); m[np.sum(~np.isnan(Q), 0) < max(2, len(P) - 1)] = np.nan
        null_max[k] = np.nanmax(m)
        if k < 300: null_all.append(m[~np.isnan(m)])
    null_all = np.concatenate(null_all)
    M[cnt < max(2, len(P) - 1)] = np.nan
    p_bin = np.array([(np.sum(null_all >= x) + 1) / (len(null_all) + 1) if not np.isnan(x) else np.nan for x in M])
    p_fwer = np.array([(np.sum(null_max >= x) + 1) / (n_perm + 1) if not np.isnan(x) else np.nan for x in M])
    # agreement: how many trains individually exceed +1 sd at this spot
    agree = np.sum(P > 1.0, 0)
    return pd.DataFrame(dict(b=np.arange(NB), s=(np.arange(NB) + 0.5) * 5, M=M, n_trains=cnt, agree=agree,
                             p=p_bin, p_fwer=p_fwer)), P

def bh(p):
    p = np.asarray(p); n = np.sum(~np.isnan(p)); q = np.full_like(p, np.nan)
    idx = np.argsort(np.where(np.isnan(p), np.inf, p))[:n]
    ranked = p[idx] * n / (np.arange(n) + 1)
    q[idx] = np.minimum.accumulate(ranked[::-1])[::-1]
    return np.minimum(q, 1)

def peaks(res, q_max=0.10, sep_m=60):
    r = res.dropna(subset=['M']).copy(); r['q'] = bh(r.p.values)
    cand = r[r.q <= q_max].sort_values('M', ascending=False)
    out = []
    for _, row in cand.iterrows():
        if all(abs(row.s - o.s) > sep_m for o in out): out.append(row)
    return pd.DataFrame(out)
