import numpy as np, pandas as pd
def repeatability(df, feats, scales=(4, 10, 20), nb=1930):
    B = np.arange(nb); T = {}
    for (trip, d), g in df.groupby(['trip', 'dir']):
        T[trip] = (d, {k: g.groupby('b')[k].median().reindex(B) for k in feats})
    trips = sorted(T); res = []
    for scale in scales:
        for k in feats:
            same, opp = [], []
            for i, a in enumerate(trips):
                for b in trips[i+1:]:
                    x = T[a][1][k].rolling(scale, center=True, min_periods=max(1, scale // 2)).mean()
                    y = T[b][1][k].rolling(scale, center=True, min_periods=max(1, scale // 2)).mean()
                    m = (x.notna() & y.notna()).values & np.isin(B, np.arange(0, nb, scale))
                    if m.sum() < 20: continue
                    c = np.corrcoef(x.values[m], y.values[m])[0, 1]
                    (same if T[a][0] == T[b][0] else opp).append(c)
            res.append(dict(scale_m=scale * 5, feat=k, same_dir=np.mean(same), opp_dir=np.mean(opp), n_same=len(same)))
    return pd.DataFrame(res)
