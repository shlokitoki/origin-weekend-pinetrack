"""Train position along the line: fuse all phones on the same train with a Kalman/RTS smoother."""
import numpy as np, pandas as pd

def group_trips(recs, gap_s=120):
    """Recordings whose time windows overlap by >50% are on the same train."""
    order = sorted(range(len(recs)), key=lambda i: recs[i]['t0'])
    trips = []
    for i in order:
        r = recs[i]; placed = False
        for tr in trips:
            a0, a1 = max(r['t0'], tr['t0']), min(r['t1'], tr['t1'])
            if (a1 - a0) > 0.5 * min(r['t1'] - r['t0'], tr['t1'] - tr['t0']):
                tr['members'].append(i); tr['t0'] = min(tr['t0'], r['t0']); tr['t1'] = max(tr['t1'], r['t1']); placed = True; break
        if not placed:
            trips.append(dict(members=[i], t0=r['t0'], t1=r['t1']))
    return trips

def kalman_chainage(t, s_meas, s_sig, v_meas, v_sig, sign, q_acc=0.6, gate=4.0):
    """1-D constant-velocity KF + RTS smoother on a 1 Hz grid.
    t: grid (s). s_meas/v_meas: arrays on grid with NaN for missing. sign: +1 westbound (s increasing), -1 eastbound."""
    n = len(t); x = np.zeros((n, 2)); P = np.zeros((n, 2, 2))
    xp = np.zeros((n, 2)); Pp = np.zeros((n, 2, 2))
    i0 = np.flatnonzero(~np.isnan(s_meas))[0]
    xk = np.array([s_meas[i0], 0.0]); Pk = np.diag([50.0**2, 5.0**2])
    for k in range(n):
        dt = 1.0 if k == 0 else t[k] - t[k-1]
        F = np.array([[1, dt], [0, 1]]); Q = q_acc**2 * np.array([[dt**4/4, dt**3/2], [dt**3/2, dt**2]])
        if k > 0:
            xk = F @ xk; Pk = F @ Pk @ F.T + Q
        xp[k], Pp[k] = xk, Pk
        # velocity update (GPS Doppler speed, signed by direction)
        if not np.isnan(v_meas[k]):
            H = np.array([[0, 1.0]]); R = v_sig[k]**2
            y = sign * v_meas[k] - xk[1]; S = (H @ Pk @ H.T)[0, 0] + R
            K = (Pk @ H.T)[:, 0] / S; xk = xk + K * y; Pk = Pk - np.outer(K, H @ Pk)
        if not np.isnan(s_meas[k]):
            H = np.array([[1.0, 0]]); R = s_sig[k]**2
            y = s_meas[k] - xk[0]; S = (H @ Pk @ H.T)[0, 0] + R
            if y**2 / S < gate**2:
                K = (Pk @ H.T)[:, 0] / S; xk = xk + K * y; Pk = Pk - np.outer(K, H @ Pk)
        x[k], P[k] = xk, Pk
    # RTS smoother
    xs = x.copy(); Ps = P.copy()
    for k in range(n - 2, -1, -1):
        dt = t[k+1] - t[k]; F = np.array([[1, dt], [0, 1]])
        C = P[k] @ F.T @ np.linalg.inv(Pp[k+1])
        xs[k] = x[k] + C @ (xs[k+1] - xp[k+1]); Ps[k] = P[k] + C @ (Ps[k+1] - Pp[k+1]) @ C.T
    return xs[:, 0], xs[:, 1], np.sqrt(Ps[:, 0, 0])

def fuse_trip(recs, members, line):
    t0 = min(recs[i]['t0'] for i in members); t1 = max(recs[i]['t1'] for i in members)
    grid = np.arange(np.floor(t0), np.ceil(t1) + 1, 1.0)
    rows = []
    for i in members:
        l = recs[i]['loc'].dropna(subset=['lat', 'lon'])
        s, d = line.project(l.lat.values, l.lon.values)
        rows.append(pd.DataFrame(dict(t=l.tabs.values, s=s, off=d, hacc=l.hacc.values, v=l.v.values)))
    g = pd.concat(rows)
    g = g[(g.off < 40) & (g.hacc < 35)]
    g['k'] = np.round(g.t - grid[0]).astype(int)
    # combine phones per second: accuracy-weighted mean position, median speed
    w = 1 / np.maximum(g.hacc, 4)**2
    g['ws'] = g.s * w; g['w'] = w
    agg = g.groupby('k').agg(ws=('ws', 'sum'), w=('w', 'sum'), v=('v', 'median'), n=('s', 'size'))
    s_meas = np.full(len(grid), np.nan); s_sig = np.full(len(grid), np.nan)
    v_meas = np.full(len(grid), np.nan); v_sig = np.full(len(grid), 0.5)
    k = agg.index.values; k = k[(k >= 0) & (k < len(grid))]; agg = agg.loc[k]
    s_meas[k] = agg.ws / agg.w; s_sig[k] = np.sqrt(1 / agg.w) + 3.0
    v_meas[k] = agg.v.values
    ds = np.nanmedian(np.diff(s_meas[~np.isnan(s_meas)][[0, -1]]))
    sign = 1 if ds > 0 else -1
    s_f, v_f, s_sd = kalman_chainage(grid, s_meas, s_sig, v_meas, v_sig, sign)
    return dict(grid=grid, s=s_f, v=v_f, s_sd=s_sd, sign=sign, direction='WB' if sign > 0 else 'EB')
