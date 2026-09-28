"""Orientation-free vibration channels + phone-handling detection for a phyphox recording."""
import numpy as np, pandas as pd
from scipy.signal import butter, sosfiltfilt

FS = 100.0

def bp(x, lo, hi, fs=FS, order=4):
    if lo is None: sos = butter(order, hi, 'low', fs=fs, output='sos')
    elif hi is None: sos = butter(order, lo, 'high', fs=fs, output='sos')
    else: sos = butter(order, [lo, hi], 'band', fs=fs, output='sos')
    return sosfiltfilt(sos, x, axis=0)

def uniform(acc):
    t = acc.tabs.values
    tg = np.arange(t[0], t[-1], 1 / FS)
    cols = ['ax', 'ay', 'az', 'gx', 'gy', 'gz']
    M = np.column_stack([np.interp(tg, t, acc[c].values) for c in cols])
    return tg, M[:, :3], M[:, 3:]

def handling_mask(ghat, w, fs=FS):
    """True where the phone is being moved/handled (not riding with the car body).
    Uses (a) fast change of gravity direction, (b) large angular rates, (c) orientation jitter."""
    lag = int(0.5 * fs)
    dang = np.degrees(np.arccos(np.clip(np.sum(ghat[lag:] * ghat[:-lag], 1), -1, 1)))
    dang = np.r_[np.zeros(lag), dang]
    wmag = np.linalg.norm(bp(w, None, 2.0), axis=1)
    bad = (dang > 1.5) | (wmag > 0.30)
    # dilate +-3 s
    k = int(3 * fs)
    c = np.convolve(bad.astype(float), np.ones(2 * k + 1), 'same') > 0
    return c

def process(rec):
    tg, a, w = uniform(rec['acc'])
    g = bp(a, None, 0.15, order=2)                       # provisional gravity (slow)
    gn = np.linalg.norm(g, axis=1, keepdims=True); ghat = g / gn
    hand0 = handling_mask(ghat, w)
    # Within each stretch where the phone is not handled, its orientation in the car is fixed, so
    # gravity is a constant vector in the phone frame: use the stretch mean (keeps the train's own
    # slow longitudinal/lateral accelerations out of the gravity estimate).
    edges = np.flatnonzero(np.diff(np.r_[0, (~hand0).astype(int), 0]))
    for i0, i1 in zip(edges[::2], edges[1::2]):
        if i1 - i0 > 20 * FS:
            m = a[i0:i1].mean(0); ghat[i0:i1] = m / np.linalg.norm(m); gn[i0:i1] = np.linalg.norm(m)
    av = np.sum(a * ghat, 1) - gn[:, 0]                  # vertical dynamic accel
    ah = a - np.sum(a * ghat, 1, keepdims=True) * ghat   # horizontal accel (3-vector, phone frame)
    yaw = np.sum(w * ghat, 1)                            # rate about vertical
    wh = w - yaw[:, None] * ghat                         # horizontal rotation (roll+pitch)
    hand = hand0
    return dict(t=tg, a=a, w=w, ghat=ghat, av=av, ah=ah, yaw=yaw, wh=wh, hand=hand)

def orient_horizontal(sig, t_kf, v_kf, sign, min_len_s=45):
    """Split horizontal accel into longitudinal/lateral using the train's own speed changes.
    For each stable (not handled) stretch, regress low-passed horizontal accel on KF longitudinal
    acceleration -> longitudinal axis in phone frame; lateral = vertical x longitudinal."""
    t = sig['t']; n = len(t)
    v = np.interp(t, t_kf, v_kf) * sign                    # forward speed (>=0)
    along = np.gradient(bp(v, None, 0.3, order=2), 1 / FS)     # forward accel
    ah_lp = bp(sig['ah'], None, 0.3, order=2)
    stable = ~sig['hand']
    # contiguous stable runs
    edges = np.flatnonzero(np.diff(np.r_[0, stable.astype(int), 0]))
    runs = list(zip(edges[::2], edges[1::2]))
    elon = np.full((n, 3), np.nan); quality = np.zeros(n)
    for i0, i1 in runs:
        if (i1 - i0) < min_len_s * FS: continue
        sl = slice(i0, i1, 10)
        X = along[sl]
        if np.std(X) < 0.08:   # no speed changes -> cannot orient
            continue
        Y = ah_lp[sl]
        b = np.linalg.lstsq(np.c_[X, np.ones_like(X)], Y, rcond=None)[0][0]  # 3-vector
        nb = np.linalg.norm(b)
        if nb < 0.3: continue
        pred = np.outer(X, b)
        r2 = 1 - np.sum((Y - pred - Y.mean(0))**2) / np.sum((Y - Y.mean(0))**2)
        elon[i0:i1] = b / nb; quality[i0:i1] = r2
    ghat = sig['ghat']
    e = elon - np.sum(elon * ghat, 1, keepdims=True) * ghat
    e = e / np.linalg.norm(e, axis=1, keepdims=True)
    elat = np.cross(ghat, e)
    alon = np.sum(sig['ah'] * e, 1); alat = np.sum(sig['ah'] * elat, 1)
    roll = np.sum(sig['w'] * e, 1); pitch = np.sum(sig['w'] * elat, 1)
    sig.update(alon=alon, alat=alat, roll=roll, pitch=pitch, orient_q=quality, v=v, along=along)
    return sig
