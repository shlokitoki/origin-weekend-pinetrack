"""Order tracking: vibration locked to wheel rotation (f = v / (pi*D)) -> wheel out-of-roundness / flats.
Also used to strip the wheel component so what remains is track-driven."""
import numpy as np
from scipy.signal import stft

NPER, HOP = 200, 25   # 2 s windows, 0.25 s hop at 100 Hz

def spectra(sig):
    f, t, Z = stft(sig['av'], fs=100, nperseg=NPER, noverlap=NPER - HOP, boundary=None, padded=False)
    P = np.abs(Z)**2
    tt = sig['t'][0] + t
    v = np.interp(tt, sig['t'], sig['v'])
    hand = np.interp(tt, sig['t'], sig['hand'].astype(float)) > 0
    s = np.interp(tt, sig['t'], sig['s'])
    return f, tt, P, v, hand, s

def order_ratio(f, P, v, D, orders=(1, 2), halfwidth=0.05):
    """Energy within +-5% of k*f_wheel vs. flanking bands (0.8-0.9 and 1.1-1.2 of k*f_wheel)."""
    fw = v / (np.pi * D)
    num = np.zeros(len(v)); den = np.zeros(len(v))
    df = f[1] - f[0]
    for k in orders:
        c = k * fw
        on = (np.abs(f[:, None] - c[None]) <= np.maximum(halfwidth * c, df))
        off = ((f[:, None] >= 0.75 * c) & (f[:, None] <= 0.88 * c)) | ((f[:, None] >= 1.12 * c) & (f[:, None] <= 1.25 * c))
        num += (P * on).sum(0) / np.maximum(on.sum(0), 1)
        den += (P * off).sum(0) / np.maximum(off.sum(0), 1)
    return num / np.maximum(den, 1e-12)

def estimate_D(f, P, v, sel, grid=np.linspace(0.60, 0.80, 81)):
    score = [np.median(np.log(order_ratio(f, P[:, sel], v[sel], D, orders=(1,)))) for D in grid]
    return grid[int(np.argmax(score))], np.array(score)

def strip_mask(f, v, D, orders=(1, 2, 3, 4), halfwidth=0.06, tones=(19.5, 29.3), tone_hw=0.8):
    """Boolean mask [freq x frame] of bins to discard: wheel orders + fixed onboard tones."""
    fw = v / (np.pi * D)
    m = np.zeros((len(f), len(v)), bool)
    for k in orders:
        c = k * fw
        m |= np.abs(f[:, None] - c[None]) <= np.maximum(halfwidth * c, 0.5)
    for tn in tones:
        m |= (np.abs(f - tn) <= tone_hw)[:, None]
    return m
