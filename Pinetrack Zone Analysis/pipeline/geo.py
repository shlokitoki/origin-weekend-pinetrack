"""E Line reference geometry (LA Metro GTFS shapes) and projection of GPS onto chainage.
Chainage s = metres along the westbound shape, 0 at Expo Park/USC, increasing toward Culver City."""
import pandas as pd, numpy as np, os
from scipy.spatial import cKDTree
G = os.path.join(os.path.dirname(__file__), '..', 'ext', 'gtfs_rail')
LAT0, LON0 = 34.018227, -118.285734  # Expo Park/USC
KX = 111320 * np.cos(np.radians(LAT0)); KY = 110574.0

def enu(lat, lon):
    return (np.asarray(lon) - LON0) * KX, (np.asarray(lat) - LAT0) * KY

def latlon(x, y):
    return LAT0 + np.asarray(y) / KY, LON0 + np.asarray(x) / KX

STATIONS = ['Expo Park/USC', 'Expo/Vermont', 'Expo/Western', 'Expo/Crenshaw', 'Farmdale',
            'Expo/La Brea', 'La Cienega/Jefferson', 'Culver City']

class Line:
    def __init__(self, shape_id='806SB_160306', margin_m=400):
        s = pd.read_csv(os.path.join(G, 'shapes.txt'))
        sh = s[s.shape_id == shape_id].sort_values('shape_pt_sequence')
        x, y = enu(sh.shape_pt_lat.values, sh.shape_pt_lon.values)
        # densify to 1 m
        d = np.r_[0, np.cumsum(np.hypot(np.diff(x), np.diff(y)))]
        dd = np.arange(0, d[-1], 1.0)
        X, Y = np.interp(dd, d, x), np.interp(dd, d, y)
        st = pd.read_csv(os.path.join(G, 'stops.txt'), dtype={'stop_id': str})
        st = st[st.stop_id.isin([str(i) for i in range(80125, 80133)])].sort_values('stop_id')
        sx, sy = enu(st.stop_lat.values, st.stop_lon.values)
        tree = cKDTree(np.c_[X, Y])
        s_st = dd[tree.query(np.c_[sx, sy])[1]]
        s0 = s_st[0]  # USC
        keep = (dd >= s0 - margin_m) & (dd <= s_st[-1] + margin_m)
        self.x, self.y, self.s = X[keep], Y[keep], dd[keep] - s0
        self.tree = cKDTree(np.c_[self.x, self.y])
        self.stations = pd.DataFrame({'name': STATIONS, 's': s_st - s0, 'lat': st.stop_lat.values, 'lon': st.stop_lon.values})
        # heading & curvature along line (for context features)
        hx, hy = np.gradient(self.x), np.gradient(self.y)
        self.heading = np.unwrap(np.arctan2(hy, hx))
        from scipy.ndimage import gaussian_filter1d
        self.curv = np.gradient(gaussian_filter1d(self.heading, 15))  # rad/m

    def project(self, lat, lon):
        x, y = enu(lat, lon)
        dist, i = self.tree.query(np.c_[x, y])
        return self.s[i], dist

    def at(self, s):
        s = np.asarray(s)
        x, y = np.interp(s, self.s, self.x), np.interp(s, self.s, self.y)
        return latlon(x, y)

    def curvature_at(self, s):
        return np.interp(s, self.s, self.curv)
