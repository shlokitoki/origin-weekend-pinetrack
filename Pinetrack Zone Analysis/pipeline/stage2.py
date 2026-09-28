"""Stage 2: Beijing-trained defect model -> transfer to E Line; line geometry from phones; priority ranking;
hotspot zones; exports (CSV + dashboard JSON)."""
import sys, os, pickle, json
sys.path.insert(0, os.path.dirname(__file__))
import numpy as np, pandas as pd
import warnings; warnings.filterwarnings('ignore')
from geo import Line
from signals import bp
from beijing import window_stats, SpeedNorm, PHONE_FEATS
from transfer import windows20, own_speed_z
from priority import segment_riders, condition_evidence, BOARDINGS
from hotspots import bh
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import roc_auc_score, average_precision_score
ROOT = os.path.join(os.path.dirname(__file__), '..'); OUT = os.path.join(ROOT, 'out')

st = pickle.load(open(os.path.join(OUT, 'stage1.pkl'), 'rb')); sigs = pickle.load(open(os.path.join(OUT, 'sigs.pkl'), 'rb'))
df = pd.read_pickle(os.path.join(OUT, 'bins_final.pkl')); L = Line()

# ---------- Beijing model ----------
tr = pd.read_pickle(os.path.join(ROOT, 'ext', 'bj_train.pkl')); te = pd.read_pickle(os.path.join(ROOT, 'ext', 'bj_test.pkl'))
Ftr, Fte = window_stats(tr), window_stats(te)
dup_frac = float(Ftr.drop(columns=['label']).round(6).duplicated().mean())
Ftr = Ftr.loc[~Ftr.drop(columns=['label']).round(6).duplicated()]
full = [c for c in Ftr.columns if c not in ('label', 'vel', 'train')]
def fit_eval(Xtr, Xte):
    m = HistGradientBoostingClassifier(max_iter=300, learning_rate=0.06, max_leaf_nodes=31, l2_regularization=1.0, random_state=0).fit(Xtr, Ftr.label)
    pr = m.predict_proba(Xte); pa = pr[:, 1:].sum(1); y = Fte.label.values
    thr = np.quantile(pa[y == 0], 0.95)
    return m, dict(auc_any=roc_auc_score(y > 0, pa), auc_severe=roc_auc_score(y == 2, pr[:, 2]), ap_any=average_precision_score(y > 0, pa),
                   recall_any_5fa=float((pa[y > 0] > thr).mean()), recall_severe_5fa=float((pa[y == 2] > thr).mean()))
_, resA = fit_eval(Ftr[full], Fte[full])
sn = SpeedNorm().fit(Ftr, PHONE_FEATS); mB, resB = fit_eval(sn.transform(Ftr), sn.transform(Fte))
bj = dict(full=resA, phone=resB, dup_frac=dup_frac, n_train_unique=int(len(Ftr)), n_test=int(len(Fte)),
          test_counts={int(k): int(v) for k, v in Fte.label.value_counts().items()})
Wn = pd.concat([windows20(s) for s in sigs.values()], ignore_index=True); Wn = own_speed_z(Wn, PHONE_FEATS).dropna()
Wn['p_defect'] = mB.predict_proba(Wn[['z_' + f for f in PHONE_FEATS]])[:, 1:].sum(1)
Wn['seg'] = (Wn.s // 20).astype(int)
Pm = Wn.groupby(['dir', 'trip', 'seg']).p_defect.median().groupby(['dir', 'seg']).mean()

# ---------- line geometry from the phones (grade, lateral tilt) ----------
Bg = np.arange(0, 9700, 10); G = []
for s in sigs.values():
    ok = ~np.isnan(s['alon']) & ~s['hand'] & (s['v'] > 2)
    if ok.mean() < 0.3: continue
    grade = (bp(np.nan_to_num(s['alon']), None, 0.2, order=2) - s['along']) / 9.81 * (1 if s['dir'] == 'WB' else -1)
    d = pd.DataFrame({'b': np.floor(s['s'] / 10).astype(int), 'g': grade})[ok]
    G.append(d.groupby('b').g.median().reindex(Bg // 10))
gm = pd.concat(G, axis=1).median(axis=1); gm = (gm - gm.median()).rolling(9, center=True, min_periods=3).mean()
grade = pd.Series(gm.values, index=Bg)

# ---------- segments ----------
cross = segment_riders(L.stations); rows = []
for d in ['EB', 'WB']:
    r = st['res'][d].copy(); r['seg'] = (r.s // 20).astype(int)
    seg = r.groupby('seg').agg(s=('s', 'mean'), M=('M', 'max'), q=('q', 'min'), p_fwer=('p_fwer', 'min'), agree=('agree', 'max'), n_tr=('n_trains', 'max')).reset_index()
    seg['p_model'] = [Pm.get((d, k), np.nan) for k in seg.seg]
    sp = df[df.dir == d].assign(seg=lambda x: (x.s // 20).astype(int)).groupby('seg').v.median(); seg['speed'] = seg.seg.map(sp)
    seg['dir'] = d; rows.append(seg)
S = pd.concat(rows, ignore_index=True); S = S[(S.s >= 0) & (S.s <= 9650)].copy()
S['grade_pct'] = np.interp(S.s, grade.index, grade.fillna(0).values) * 100
S['lat'], S['lon'] = L.at(S.s.values)
S['riders_per_day'] = [cross(s) for s in S.s]
stn = L.stations
S['nearest_station'] = [stn.name[np.argmin(np.abs(stn.s - s))] for s in S.s]
S['m_from_station'] = [s - stn.s[np.argmin(np.abs(stn.s - s))] for s in S.s]
# real ramps / aerial approaches: stretches where |grade| > 1.5% that peak above 3% (smaller wiggles are sensor noise)
_g = np.abs(grade.fillna(0).values); _s = grade.index.values; _ed = np.flatnonzero(np.diff(np.r_[0, (_g > 0.015).astype(int), 0]))
RAMPS = [(float(_s[i0]), float(_s[i1 - 1])) for i0, i1 in zip(_ed[::2], _ed[1::2]) if _g[i0:i1].max() > 0.03]
def dist_to_ramp(a, b): return min((max(0.0, r0 - b, a - r1) for r0, r1 in RAMPS), default=1e9)
S['near_ramp'] = [dist_to_ramp(s, s) <= 150 for s in S.s]
S['edge'] = (S.s < 150) | (S.s > 9500)
S['evidence'] = condition_evidence(S.M, S.q, S.p_model, S.agree, S.n_tr)
S.loc[S.edge | (S.n_tr < 2), 'evidence'] = np.nan
vmax = np.nanmax(S.speed)
S['consequence'] = 0.5 * S.riders_per_day / S.riders_per_day.max() + 0.3 * (np.nan_to_num(S.speed) / vmax)**2 + 0.2 * S.near_ramp
S['priority'] = S.evidence * S.consequence

# ---------- hotspot zones (cluster strong segments across both tracks) ----------
cand = S[S.evidence >= 0.40].sort_values('s')
zones = []; cur = []
for _, r in cand.iterrows():
    if cur and r.s - cur[-1].s > 250: zones.append(cur); cur = []
    cur.append(r)
if cur: zones.append(cur)
Z = []
for zs in zones:
    z = pd.DataFrame(zs); best = z.sort_values('evidence', ascending=False).iloc[0]
    tier = 1 if (z.q <= 0.10).any() else 2
    both = z.dir.nunique() == 2
    side = 'west' if best.m_from_station > 0 else 'east'
    Z.append(dict(s_from=float(z.s.min()), s_to=float(z.s.max()), s_peak=float(best.s), lat=float(best.lat), lon=float(best.lon),
                  where=f"{abs(best.m_from_station):.0f} m {side} of {best.nearest_station}", dirs='+'.join(sorted(z.dir.unique())),
                  both_tracks=bool(both), tier=int(tier), evidence=float(z.evidence.max()), M=float(z.M.max()),
                  q=float(np.nanmin(z.q)), p_fwer=float(np.nanmin(z.p_fwer)), trains_agree=int(z.agree.max()), n_trains=int(z.n_tr.max()),
                  p_model=float(np.nanmax(z.p_model)), speed=float(np.nanmedian(z.speed)), near_ramp=bool(z.near_ramp.any()),
                  riders=float(best.riders_per_day)))
Z = pd.DataFrame(Z)
# zone-level near-ramp and priority at the dashboard's default weights (riders 50, speed 30, structure 20)
Z['near_ramp'] = [dist_to_ramp(a, b) <= 150 for a, b in zip(Z.s_from, Z.s_to)]
Z['priority'] = Z.evidence * (0.5 * Z.riders / S.riders_per_day.max() + 0.3 * (Z.speed / np.nanmax(S.speed))**2 + 0.2 * Z.near_ramp)
# zone numbers: confirmed first, then by strength of evidence (repair order is a separate ranking by priority)
Z = Z.sort_values(['tier', 'evidence'], ascending=[True, False]).reset_index(drop=True); Z.index += 1

S.to_csv(os.path.join(OUT, 'segments_20m.csv'), index=False); Z.to_csv(os.path.join(OUT, 'hotspot_zones.csv'), index_label='rank')
pickle.dump(dict(S=S, Z=Z, bj=bj, grade=grade, Wn=Wn, ramps=RAMPS), open(os.path.join(OUT, 'stage2.pkl'), 'wb'))
print(Z.round(3).to_string()); print(json.dumps(bj, indent=1, default=float))
