"""Train a track-geometry-defect classifier on the Beijing Subway car-body dataset (CC-BY, Wang et al. 2022/2023)
and a 'phone-compatible' variant using only channels a phone gives us, in speed-normalised relative units."""
import numpy as np, pandas as pd
from scipy.stats import kurtosis

def window_stats(d):
    g = d.groupby('ID')
    z = d.acc_z - 0.535
    d = d.assign(vz=z, absz=z.abs(), rot=np.hypot(d.anglerate_x, d.anglerate_y))
    g = d.groupby('ID')
    F = pd.DataFrame({
        'v_std': g.vz.std(), 'v_max': g.absz.max(), 'v_p90': g.absz.quantile(0.9), 'v_kurt': g.vz.apply(lambda x: kurtosis(x)),
        'lat_mean': g.acc_y.mean(), 'lat_max': g.acc_y.max(),
        'roll_mean': g.anglerate_x.mean(), 'roll_max': g.anglerate_x.max(),
        'pitch_mean': g.anglerate_y.mean(), 'pitch_max': g.anglerate_y.max(),
        'yaw_mean': g.anglerate_z.mean(), 'yaw_std': g.anglerate_z.std(),
        'rot_mean': g.rot.mean(), 'rot_max': g.rot.max(),
        'vel': g.velocity.mean(), 'train': g.train_num.first(), 'label': g.label.first()})
    return F

PHONE_FEATS = ['v_std', 'v_max', 'lat_mean', 'lat_max', 'rot_mean', 'rot_max']

class SpeedNorm:
    """log(feature) -> robust z relative to defect-free windows at similar speed (same idea as the phone pipeline)."""
    def fit(self, F, feats, nb=10):
        ref = F[F.label == 0]
        self.edges = np.quantile(ref.vel, np.linspace(0, 1, nb + 1)); self.feats = feats; self.stats = {}
        idx = np.clip(np.searchsorted(self.edges, ref.vel) - 1, 0, nb - 1)
        for f in feats:
            lx = np.log(ref[f] + 1e-4)
            self.stats[f] = [(np.median(lx[idx == j]), 1.4826 * np.median(np.abs(lx[idx == j] - np.median(lx[idx == j])))) for j in range(nb)]
        return self
    def transform(self, F):
        nb = len(self.edges) - 1; idx = np.clip(np.searchsorted(self.edges, F.vel) - 1, 0, nb - 1)
        out = pd.DataFrame(index=F.index)
        for f in self.feats:
            m = np.array([self.stats[f][j][0] for j in idx]); s = np.array([self.stats[f][j][1] for j in idx])
            out['z_' + f] = (np.log(F[f] + 1e-4) - m) / s
        return out
