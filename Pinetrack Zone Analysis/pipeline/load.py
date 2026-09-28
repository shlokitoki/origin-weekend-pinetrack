"""Load phyphox exports (converted to pickles) into clean, absolute-time arrays."""
import pandas as pd, numpy as np, glob, os

DATA = os.path.join(os.path.dirname(__file__), '..', 'data')

# Trip grouping (from phyphox system-time metadata; same train = same trip)
PHONE = {  # recording -> phone label (from deviceModel + recording names)
    'Track_Scan': 'Phone A (iPhone 16 Pro)', 'track2': 'Phone A (iPhone 16 Pro)',
    'track_suhela': 'Suhela (iPhone 16 Pro)',
    'track_brooke': 'Brooke (iPhone 17)', '3': 'Brooke (iPhone 17)',
    'Track_record_arjan': 'Arjan (iPhone 16 Plus)',
}

def phone_of(name):
    for k, v in PHONE.items():
        if name.startswith(k + '_') or name.split('_2026')[0] == k:
            return v
    return 'unknown'

def list_recordings():
    return sorted(set(os.path.basename(f).split('__')[0] for f in glob.glob(os.path.join(DATA, '*__Accelerometer.pkl'))))

def _time_segments(mt):
    """Return list of (exp_start, exp_end, sys_offset) for each recorded (un-paused) segment."""
    segs = []
    ev = mt.values.tolist()
    cur = None
    for e, texp, tsys, _ in ev:
        if e == 'START':
            cur = (texp, tsys - texp)
        elif e == 'PAUSE' and cur is not None:
            segs.append((cur[0], texp, cur[1])); cur = None
    if cur is not None:
        segs.append((cur[0], np.inf, cur[1]))
    return segs

def load(name, min_seg_s=60):
    rd = lambda k: pd.read_pickle(os.path.join(DATA, f'{name}__{k}.pkl'))
    acc, gyr, loc, mt, md = rd('Accelerometer'), rd('Gyroscope'), rd('Location'), rd('Metadata_Time'), rd('Metadata_Device')
    acc.columns = ['t', 'ax', 'ay', 'az']; gyr.columns = ['t', 'gx', 'gy', 'gz']
    loc.columns = ['t', 'lat', 'lon', 'h', 'v', 'dir', 'hacc', 'vacc']
    loc = loc.apply(pd.to_numeric, errors='coerce')
    segs = [s for s in _time_segments(mt) if (min(s[1], acc.t.max()) - s[0]) >= min_seg_s]
    # keep the longest usable segment (short resumes at the end are dropped)
    s0, s1, off = max(segs, key=lambda s: min(s[1], acc.t.max()) - s[0])
    def cut(df):
        d = df[(df.t >= s0) & (df.t < s1)].copy(); d['tabs'] = d.t + off; return d.reset_index(drop=True)
    acc, gyr, loc = cut(acc), cut(gyr), cut(loc)
    # put gyro on accelerometer clock
    for c in ['gx', 'gy', 'gz']:
        acc[c] = np.interp(acc.t, gyr.t, gyr[c])
    meta = dict(zip(md.property, md.value))
    return dict(name=name, acc=acc, loc=loc, model=meta.get('deviceModel'), phone=phone_of(name),
                t0=acc.tabs.iloc[0], t1=acc.tabs.iloc[-1])
