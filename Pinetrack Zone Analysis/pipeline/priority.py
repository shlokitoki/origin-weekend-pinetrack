"""Condition evidence x consequence -> priority. Consequence uses FY2025 station boardings (Wikipedia/LA Metro),
a gravity origin-destination model, measured train speed, and ramp/structure zones found by the phones themselves."""
import numpy as np, pandas as pd

BOARDINGS = {  # FY2025 average weekday boardings (Wikipedia station infoboxes; La Brea is FY2024)
    'Expo Park/USC': 1318, 'Expo/Vermont': 2730, 'Expo/Western': 2620, 'Expo/Crenshaw': 3740,
    'Farmdale': 910, 'Expo/La Brea': 1453, 'La Cienega/Jefferson': 1476, 'Culver City': 2012}
LINE_WEEKDAY = 54006          # E Line weekday riders, March 2026 (Wikipedia, citing LA Metro)
EAST_SHARE = 0.60             # ASSUMPTION: share of remaining boardings east of USC (downtown + Eastside)

def segment_riders(stations):
    rest = LINE_WEEKDAY - sum(BOARDINGS.values())
    nodes = [('Downtown & East', -1e9, rest * EAST_SHARE)] + \
            [(n, s, BOARDINGS[n]) for n, s in zip(stations.name, stations.s)] + \
            [('Westside', 1e9, rest * (1 - EAST_SHARE))]
    B = np.array([b for _, _, b in nodes]); S = np.array([s for _, s, _ in nodes]); tot = B.sum()
    def crossing(s):
        east = S < s; west = ~east
        return (B[east].sum() * B[west].sum() / tot)   # riders per direction per weekday
    return crossing

def condition_evidence(M, q, p_model, agree, n_tr):
    """0-1 evidence that a location is abnormal: blends the repeatability index (sigmoid of mean z),
    statistical significance, and the Beijing-trained defect model."""
    m = 1 / (1 + np.exp(-(np.nan_to_num(M) - 1.0) * 2.5))
    sig = np.where(np.nan_to_num(q, nan=1) <= 0.10, 1.0, np.where(np.nan_to_num(q, nan=1) <= 0.25, 0.6, 0.3))
    pm = np.clip(np.nan_to_num(p_model) / 0.5, 0, 1)
    return np.clip(0.45 * m + 0.25 * sig * m + 0.30 * pm, 0, 1)
