"""End-to-end pipeline: phyphox exports -> positions -> vibration features -> wheel check -> hotspots ->
Beijing-trained defect model -> priority ranking -> outputs (CSV + dashboard JSON).

Usage:  python pipeline/run_all.py --xlsx-dir <folder with phyphox .xlsx exports>
Requires: ext/gtfs_rail (git clone https://github.com/LACMTA/gtfs_rail) and, for the defect model,
          ext/bj_train.pkl / ext/bj_test.pkl (from https://github.com/Elscip/scidata_jrrt_1, see README)."""
import sys, os, glob, argparse, pickle, json
sys.path.insert(0, os.path.dirname(__file__))
import numpy as np, pandas as pd
import warnings; warnings.filterwarnings('ignore')
ROOT = os.path.join(os.path.dirname(__file__), '..'); OUT = os.path.join(ROOT, 'out'); os.makedirs(OUT, exist_ok=True)

def step(msg): print(f'[pipeline] {msg}', flush=True)

def convert(xlsx_dir):
    from concurrent.futures import ProcessPoolExecutor
    os.makedirs(os.path.join(ROOT, 'data'), exist_ok=True)
    files = sorted(glob.glob(os.path.join(xlsx_dir, '*.xlsx')))
    with ProcessPoolExecutor(4) as ex: list(ex.map(_conv, files))

def _conv(f):
    base = os.path.basename(f).replace('.xlsx', '')
    name = base.split('_', 1)[1] if base.split('_', 1)[0].count('-') == 1 else base   # strip upload prefix if present
    for k, df in pd.read_excel(f, sheet_name=None, engine='openpyxl').items():
        df.to_pickle(os.path.join(ROOT, 'data', f"{name}__{k.replace(' ', '_')}.pkl"))

def main(a):
    from load import list_recordings, load
    from geo import Line
    from position import group_trips, fuse_trip
    from signals import process, orient_horizontal
    from features2 import frame_features, bin_frames, FEATS
    from features import speed_normalize
    from wheel import spectra, estimate_D, order_ratio
    from hotspots import COMPOSITE, detect, peaks, bh, NB
    from repeat import repeatability

    if a.xlsx_dir: step('converting xlsx'); convert(a.xlsx_dir)
    step('loading recordings'); recs = [load(n) for n in list_recordings()]
    L = Line()
    step('grouping phones into trains and fusing positions'); trips = group_trips(recs)
    for tr in trips: tr.update(fuse_trip(recs, tr['members'], L))
    trip_of = {i: j for j, tr in enumerate(trips) for i in tr['members']}
    step('vibration channels, handling mask, orientation'); sigs = {}
    for i, r in enumerate(recs):
        tr = trips[trip_of[i]]
        s = orient_horizontal(process(r), tr['grid'], tr['v'], tr['sign'])
        s.update(s=np.interp(s['t'], tr['grid'], tr['s']), trip=trip_of[i], dir=tr['direction'], name=r['name'], phone=r['phone'])
        sigs[i] = s
    step('wheel order tracking'); wrows = []
    for i, s in sigs.items():
        f, tt, P, v, hand, sc = spectra(s); sel = (v > 12) & ~hand
        D, _ = estimate_D(f, P, v, sel); r1 = order_ratio(f, P[:, sel], v[sel], 0.711, orders=(1,))
        wrows.append(dict(trip=s['trip'], dir=s['dir'], name=s['name'], phone=s['phone'], D_est_m=D, order1_ratio=float(np.median(r1)),
                          t_start=recs[i]['t0']))
    W = pd.DataFrame(wrows)
    step('distance-domain features (wheel orders + onboard tones removed)')
    df = pd.concat([bin_frames(frame_features(s), s) for s in sigs.values()], ignore_index=True)
    df = speed_normalize(df, feats=FEATS, min_n=1)
    # remove traction/braking influence per recording
    acc = []
    for s in sigs.values():
        d = pd.DataFrame({'b': np.floor(s['s'] / 5).astype(int), 'a': s['along'], 'v': s['v']})
        g = d[d.v > 3].groupby('b').a.mean(); acc.append(pd.DataFrame({'b': g.index, 'acc': g.values, 'name': s['name']}))
    df = df.merge(pd.concat(acc), on=['name', 'b'], how='left'); df['comp'] = df[COMPOSITE].mean(axis=1)
    def adj(g):
        g = g.copy(); m = g.comp.notna() & g.acc.notna()
        X = np.c_[np.ones(m.sum()), g.acc[m], np.abs(g.acc[m])]; beta = np.linalg.lstsq(X, g.comp[m], rcond=None)[0]
        g.loc[m, 'comp_adj'] = g.comp[m] - X[:, 1:] @ beta[1:]; return g
    df = pd.concat([adj(g) for _, g in df.groupby('name')], ignore_index=True)
    df.to_pickle(os.path.join(OUT, 'bins_final.pkl'))
    step('repeatability'); rep = repeatability(df.assign(z_comp=df.comp_adj), ['z_comp', 'z_v_high', 'z_v_struct', 'z_v_struct_raw', 'z_v_body'])
    step('hotspot detection with permutation test')
    B = np.arange(NB); prof = {}
    for (trip, d), g in df.groupby(['trip', 'dir']):
        p = g.groupby('b').comp_adj.median().reindex(B); prof[trip] = (d, p.rolling(4, center=True, min_periods=2).mean().values)
    res = {}
    for d in ['EB', 'WB']:
        r, P = detect(prof, d, n_perm=a.n_perm); rr = r.dropna(subset=['M']).copy(); rr['q'] = bh(rr.p.values)
        res[d] = r.merge(rr[['b', 'q']], on='b', how='left')
    pickle.dump(dict(recs=[{k: v for k, v in r.items() if k not in ('acc', 'loc')} for r in recs], trips=trips, prof=prof, res=res, W=W, rep=rep),
                open(os.path.join(OUT, 'stage1.pkl'), 'wb'))
    pickle.dump(sigs, open(os.path.join(OUT, 'sigs.pkl'), 'wb'), protocol=4)
    step('done stage 1')

if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('--xlsx-dir', default=None); ap.add_argument('--n-perm', type=int, default=3000)
    main(ap.parse_args())
