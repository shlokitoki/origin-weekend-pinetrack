"""Synthetic-defect injection test (run after run_all.py). Plants car-body jolts of known size into the raw
eastbound accelerometer data at random spots, re-runs features + detection, and reports the recovery rate."""
import sys, os, pickle
sys.path.insert(0, os.path.dirname(__file__))
import numpy as np, pandas as pd, warnings; warnings.filterwarnings('ignore')
from inject import inject, local_frames
from features2 import bin_frames, FEATS
from features import speed_normalize
from hotspots import COMPOSITE, detect, bh, NB
from geo import Line
OUT = os.path.join(os.path.dirname(__file__), '..', 'out')
sigs = pickle.load(open(os.path.join(OUT, 'sigs.pkl'), 'rb')); base = pd.read_pickle(os.path.join(OUT, 'bins_final.pkl'))
rawcols = [c for c in base.columns if not c.startswith('z_') and c not in ('comp', 'comp_adj', 'acc')]
eb = [i for i, s in sigs.items() if s['dir'] == 'EB']; L = Line(); rng = np.random.default_rng(42)
KNOWN = [4157, 4302, 7692]   # existing confirmed hotspots: keep planted defects >250 m away so they aren't confused
cands = [s for s in np.arange(300, 9300, 10) if np.min(np.abs(L.stations.s.values - s)) > 150 and all(abs(s - h) > 250 for h in KNOWN)]
locs = rng.choice(cands, 24, replace=False); rows = []
for amp in [0.15, 0.3, 0.6, 1.2]:
    for s0 in locs:
        d = base[rawcols].copy()
        for i in eb:
            r = inject(sigs[i], s0, amp, rng)
            if r is None: continue
            nb = bin_frames(local_frames(*r), sigs[i]); key = d.name == sigs[i]['name']
            d = pd.concat([d[~(key & d.b.isin(nb.b))], nb[rawcols]], ignore_index=True)
        d = speed_normalize(d, feats=FEATS, min_n=1); d['comp'] = d[COMPOSITE].mean(axis=1)
        B = np.arange(NB); prof = {}
        for (trip, dd), g in d.groupby(['trip', 'dir']):
            prof[trip] = (dd, g.groupby('b').comp.median().reindex(B).rolling(4, center=True, min_periods=2).mean().values)
        res, _ = detect(prof, 'EB', n_perm=400, seed=1); r2 = res.dropna(subset=['M']).copy(); r2['q'] = bh(r2.p.values)
        w = r2[np.abs(r2.s - s0) < 30]
        rows.append(dict(amp=amp, s0=s0, detected=bool((w.q <= 0.10).any()), M=w.M.max()))
    print(f'amp {amp} m/s2 done', flush=True)
R = pd.DataFrame(rows); R.to_csv(os.path.join(OUT, 'injection_results.csv'), index=False)
print(R.groupby('amp').agg(detection_rate=('detected', 'mean'), median_M=('M', 'median')))
