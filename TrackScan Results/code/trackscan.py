#!/usr/bin/env python3
"""
TrackScan: turn phyphox train recordings into a ranked list of rough-track hotspots.

Usage:
    python3 trackscan.py <folder_with_recordings> <output_folder> [eline.json]

Input: phyphox exports (Excel .xlsx, CSV .zip, or loose .csv) that contain
       accelerometer data AND location (GPS) data from the same recording.
Output: runs_summary.csv, windows.csv, bins.csv, hotspots.csv, profile.png, results.json
"""
import sys, os, glob, json, zipfile, io, math, re
import numpy as np
import pandas as pd
from scipy.signal import butter, sosfiltfilt

# ---------------------------------------------------------------- geometry
LAT0 = 34.03
M_LAT = 110_950.0
M_LON = 111_320.0 * math.cos(math.radians(LAT0))


def to_xy(lat, lon):
    return np.asarray(lon) * M_LON, np.asarray(lat) * M_LAT


class Line:
    """Polyline of the track; projects GPS points to 'meters along the line'."""

    def __init__(self, latlon):
        latlon = np.asarray(latlon, float)
        self.lat, self.lon = latlon[:, 0], latlon[:, 1]
        x, y = to_xy(self.lat, self.lon)
        self.x, self.y = x, y
        seg = np.hypot(np.diff(x), np.diff(y))
        self.cum = np.concatenate([[0], np.cumsum(seg)])
        self.length = self.cum[-1]

    def project(self, lat, lon):
        px, py = to_xy(lat, lon)
        px, py = np.atleast_1d(px)[:, None], np.atleast_1d(py)[:, None]
        ax, ay = self.x[:-1][None, :], self.y[:-1][None, :]
        bx, by = self.x[1:][None, :], self.y[1:][None, :]
        dx, dy = bx - ax, by - ay
        L2 = dx * dx + dy * dy
        L2[L2 == 0] = 1e-9
        t = np.clip(((px - ax) * dx + (py - ay) * dy) / L2, 0, 1)
        cx, cy = ax + t * dx, ay + t * dy
        d = np.hypot(px - cx, py - cy)
        i = np.argmin(d, axis=1)
        rows = np.arange(len(i))
        s = self.cum[i] + t[rows, i] * np.sqrt(L2[0, i])
        return s, d[rows, i]

    def point_at(self, s):
        s = np.clip(s, 0, self.length)
        return np.interp(s, self.cum, self.lat), np.interp(s, self.cum, self.lon)


# ---------------------------------------------------------------- loading
def read_tables(path):
    """Return {table_name: DataFrame} from an xlsx / zip-of-csv / csv export."""
    ext = os.path.splitext(path)[1].lower()
    tables = {}
    if ext in (".xlsx", ".xls"):
        cache = path + ".pkl"
        if os.path.exists(cache) and os.path.getmtime(cache) >= os.path.getmtime(path):
            return pd.read_pickle(cache)
        for name, df in pd.read_excel(path, sheet_name=None).items():
            tables[name] = df
        try:
            pd.to_pickle(tables, cache)
        except OSError:
            pass
    elif ext == ".zip":
        with zipfile.ZipFile(path) as z:
            for n in z.namelist():
                if n.lower().endswith(".csv"):
                    raw = z.read(n)
                    tables[n] = _read_csv_bytes(raw)
    elif ext in (".csv", ".tsv", ".txt"):
        with open(path, "rb") as f:
            tables[os.path.basename(path)] = _read_csv_bytes(f.read())
    return tables


def _read_csv_bytes(raw):
    text = raw.decode("utf-8", errors="replace")
    first = text.splitlines()[0] if text else ""
    sep = "\t" if "\t" in first else (";" if first.count(";") > first.count(",") else ",")
    dec = "," if sep in (";", "\t") and re.search(r"\d,\d", text[:2000]) and sep != "," else "."
    return pd.read_csv(io.StringIO(text), sep=sep, decimal=dec)


def _col(df, *must, avoid=()):
    for c in df.columns:
        lc = str(c).lower()
        if all(m in lc for m in must) and not any(a in lc for a in avoid):
            return c
    return None


def find_acc(tables):
    best = None
    for name, df in tables.items():
        lname = name.lower()
        if any(k in lname for k in ("gyro", "magnet", "location", "metadata", "linear", "gravity")):
            continue
        tcol = _col(df, "time")
        cols = {}
        for ax in "xyz":
            c = None
            for col in df.columns:
                lc = str(col).lower()
                if "rad" in lc or "µt" in lc or "ut)" in lc:
                    continue
                if re.search(rf"(^|[^a-z]){ax}([^a-z]|$)", lc) and ("m/s" in lc or "acc" in lc):
                    c = col
                    break
            cols[ax] = c
        if tcol is not None and all(cols.values()):
            score = 2 if "acc" in lname else 1
            if best is None or score > best[0]:
                best = (score, df, tcol, cols)
    if best is None:
        return None
    _, df, tcol, cols = best
    out = pd.DataFrame({"t": df[tcol], "ax": df[cols["x"]], "ay": df[cols["y"]], "az": df[cols["z"]]})
    return out.apply(pd.to_numeric, errors="coerce").dropna()


def find_gps(tables):
    for name, df in tables.items():
        lat, lon, t = _col(df, "lat"), _col(df, "lon"), _col(df, "time")
        if lat is not None and lon is not None and t is not None:
            out = pd.DataFrame({"t": df[t], "lat": df[lat], "lon": df[lon]})
            v = _col(df, "veloc") or _col(df, "speed")
            acc = _col(df, "horizontal") or _col(df, "accuracy", avoid=("vertical",))
            out["v"] = df[v] if v is not None else np.nan
            out["hacc"] = df[acc] if acc is not None else np.nan
            out = out.apply(pd.to_numeric, errors="coerce")
            return out.dropna(subset=["t", "lat", "lon"])
    return None


def find_start_time(tables):
    for name, df in tables.items():
        if "time" in name.lower() and ("meta" in name.lower()):
            ev = _col(df, "event")
            st = _col(df, "system time", avoid=("text",))
            if ev is not None and st is not None:
                rows = df[df[ev].astype(str).str.upper() == "START"]
                if len(rows):
                    try:
                        return float(rows.iloc[0][st])
                    except Exception:
                        pass
    return None


# ---------------------------------------------------------------- per-run processing
WINDOW_S = 1.0
MIN_SPEED = 3.0  # m/s; drop station dwell / walking
MAX_OFFSET = 60.0  # m from track centerline
MAX_GPS_GAP = 4.0  # s
ACCEL_THR = 0.3  # m/s^2; |speed change| above this = braking/accelerating
STOP_BUFFER_S = 10.0  # s before a stop / after a start treated as braking / accelerating


def process_run(path, line):
    tables = read_tables(path)
    acc, gps = find_acc(tables), find_gps(tables)
    info = {"file": os.path.basename(path)}
    if acc is None or len(acc) < 200:
        info["error"] = "no accelerometer data found"
        return info, None
    if gps is None or len(gps) < 10:
        info["error"] = "no GPS/location data found"
        return info, None

    acc = acc.sort_values("t").drop_duplicates("t")
    dt = np.median(np.diff(acc["t"].values))
    fs = 1.0 / dt if dt > 0 else 100.0
    info["sample_rate_hz"] = round(fs, 1)

    # vertical = component along gravity (robust to a tilted phone)
    t0, t1 = acc["t"].iloc[0], acc["t"].iloc[-1]
    tu = np.arange(t0, t1, dt)
    A = np.vstack([np.interp(tu, acc["t"].values, acc[k].values) for k in ("ax", "ay", "az")])
    lp = butter(2, 0.3, btype="low", fs=fs, output="sos")
    G = sosfiltfilt(lp, A, axis=1)
    gn = np.linalg.norm(G, axis=0)
    gn[gn == 0] = 1e-9
    sig = (A * G).sum(axis=0) / gn
    means = A.mean(axis=1)
    info["tilt_deg"] = round(float(np.degrees(np.arccos(min(1.0, abs(means[2]) / np.linalg.norm(means))))), 1)
    hi = min(30.0, 0.45 * fs)
    sos = butter(4, [1.0, hi], btype="band", fs=fs, output="sos")
    filt = sosfiltfilt(sos, sig - sig.mean())

    n = int(WINDOW_S * fs)
    nw = len(filt) // n
    if nw < 10:
        info["error"] = "recording too short"
        return info, None
    seg = filt[: nw * n].reshape(nw, n)
    rms = np.sqrt((seg ** 2).mean(axis=1))
    peak = np.abs(seg).max(axis=1)
    tc = tu[: nw * n].reshape(nw, n).mean(axis=1)

    # GPS -> window centers
    gps = gps.sort_values("t")
    if gps["hacc"].notna().any():
        gps = gps[(gps["hacc"].isna()) | (gps["hacc"] <= 40)]
    gps = gps.drop_duplicates("t")
    info["gps_fixes"] = int(len(gps))
    gt = gps["t"].values
    lat = np.interp(tc, gt, gps["lat"].values)
    lon = np.interp(tc, gt, gps["lon"].values)
    idx = np.clip(np.searchsorted(gt, tc), 1, len(gt) - 1)
    gap = np.minimum(np.abs(gt[idx] - tc), np.abs(gt[idx - 1] - tc))
    ok = gap <= MAX_GPS_GAP

    s, off = line.project(lat, lon)
    ok &= off <= MAX_OFFSET

    # speed along the line (smoothed)
    sp = pd.Series(s).where(ok)
    ds = sp.diff() / np.diff(np.concatenate([[tc[0] - WINDOW_S], tc]))
    speed = ds.abs().rolling(5, center=True, min_periods=2).median().values
    if gps["v"].notna().sum() > len(gps) * 0.5:
        gv = np.interp(tc, gt, gps["v"].fillna(-1).values)
        speed = np.where(gv >= 0, gv, speed)
    # --- braking / accelerating detection (operator brakes before every stop) ---
    sp_s = pd.Series(speed).interpolate(limit=5, limit_direction="both")
    sp_s = sp_s.rolling(3, center=True, min_periods=1).mean().values
    along = np.gradient(np.nan_to_num(sp_s), tc)  # longitudinal accel, m/s^2
    stopped = np.nan_to_num(sp_s) < 1.0
    stop_t = tc[stopped]
    if len(stop_t):
        nxt = np.searchsorted(stop_t, tc)
        t_to_stop = np.where(nxt < len(stop_t), stop_t[np.minimum(nxt, len(stop_t) - 1)] - tc, np.inf)
        prv = nxt - 1
        t_since_stop = np.where(prv >= 0, tc - stop_t[np.maximum(prv, 0)], np.inf)
    else:
        t_to_stop = np.full(len(tc), np.inf)
        t_since_stop = np.full(len(tc), np.inf)
    phase = np.full(len(tc), "cruise", dtype=object)
    phase[(along > ACCEL_THR) | (t_since_stop <= STOP_BUFFER_S)] = "accelerating"
    phase[(along < -ACCEL_THR) | (t_to_stop <= STOP_BUFFER_S)] = "braking"

    ok &= np.nan_to_num(speed) >= MIN_SPEED

    w = pd.DataFrame({"t": tc, "s": s, "offset": off, "lat": lat, "lon": lon,
                      "speed": speed, "long_acc": along, "phase": phase,
                      "rms": rms, "peak": peak})[ok].copy()
    if len(w) < 20:
        info["error"] = "too few moving points on the E Line (check GPS / route)"
        return info, None

    trend = np.polyfit(w["t"], w["s"], 1)[0]
    info["direction"] = "westbound" if trend > 0 else "eastbound"
    info["from_m"], info["to_m"] = float(w["s"].min()), float(w["s"].max())
    info["covered_km"] = round((info["to_m"] - info["from_m"]) / 1000, 2)
    info["moving_windows"] = int(len(w))
    st = find_start_time(tables)
    if st:
        info["start_epoch"] = st
        info["start_local"] = pd.to_datetime(st, unit="s", utc=True).tz_convert("America/Los_Angeles").strftime("%H:%M:%S")
    return info, w


# ---------------------------------------------------------------- across runs
BIN_M = 25.0


def analyze(folder, outdir, line_json):
    os.makedirs(outdir, exist_ok=True)
    geo = json.load(open(line_json))
    line = Line(geo["shape"])
    st_lat = [x["lat"] for x in geo["stations"]]
    st_lon = [x["lon"] for x in geo["stations"]]
    st_s, _ = line.project(np.array(st_lat), np.array(st_lon))
    stations = [{"name": x["name"].replace(" Station", ""), "s": float(v)} for x, v in zip(geo["stations"], st_s)]

    files = sorted(sum([glob.glob(os.path.join(folder, "**", p), recursive=True)
                        for p in ("*.xlsx", "*.xls", "*.zip", "*.csv")], []))
    infos, wins = [], []
    for i, f in enumerate(files):
        try:
            info, w = process_run(f, line)
        except Exception as e:  # keep going on bad files
            info, w = {"file": os.path.basename(f), "error": f"{type(e).__name__}: {e}"}, None
        info["run"] = f"R{i + 1:02d}"
        infos.append(info)
        if w is not None:
            w["run"] = info["run"]
            wins.append(w)
        print(info)
    summary = pd.DataFrame(infos)
    summary.to_csv(os.path.join(outdir, "runs_summary.csv"), index=False)
    if not wins:
        print("No usable runs.")
        return None

    W = pd.concat(wins, ignore_index=True)
    W.to_csv(os.path.join(outdir, "windows_all_phases.csv"), index=False)
    ph = W["phase"].value_counts(normalize=True).round(3).to_dict()
    print("phase share of moving seconds:", ph)
    if os.environ.get("CRUISE_ONLY", "1") == "1":
        W = W[W["phase"] == "cruise"].copy()
    # speed correction: vibration grows with speed; fit a power law and divide it out
    good = (W["rms"] > 0) & (W["speed"] > 0)
    b, a = np.polyfit(np.log(W.loc[good, "speed"]), np.log(W.loc[good, "rms"]), 1)
    b = float(np.clip(b, 0, 2))
    W["adj"] = W["rms"] / np.power(W["speed"], b)
    # per-run normalization (different phones / placements have different sensitivity)
    W["score"] = W["adj"] / W.groupby("run")["adj"].transform("median")
    W["bin"] = (W["s"] // BIN_M).astype(int)
    W.to_csv(os.path.join(outdir, "windows.csv"), index=False)

    per = W.groupby(["bin", "run"])["score"].max().unstack("run")
    run_p90 = W.groupby("run")["score"].quantile(0.90)
    hot = per.ge(run_p90, axis=1) & per.notna()
    B = pd.DataFrame({
        "bin": per.index,
        "s_start": per.index * BIN_M,
        "runs": per.notna().sum(axis=1).values,
        "median_score": per.median(axis=1, skipna=True).values,
        "hot_frac": (hot.sum(axis=1) / per.notna().sum(axis=1)).values,
    })
    lat, lon = line.point_at(B["s_start"].values + BIN_M / 2)
    B["lat"], B["lon"] = lat, lon
    B.to_csv(os.path.join(outdir, "bins.csv"), index=False)

    nruns = W["run"].nunique()
    min_runs = max(2, int(math.ceil(0.5 * nruns)))
    cand = B[(B["runs"] >= min_runs) & (B["hot_frac"] >= 0.5) & (B["median_score"] >= 1.5)].copy()

    # merge adjacent bins into segments
    hotspots = []
    if len(cand):
        cand = cand.sort_values("bin")
        groups = (cand["bin"].diff() != 1).cumsum()
        for _, g in cand.groupby(groups):
            s0, s1 = g["s_start"].min(), g["s_start"].max() + BIN_M
            mid = (s0 + s1) / 2
            la, lo = line.point_at(mid)
            before = [x for x in stations if x["s"] <= mid]
            after = [x for x in stations if x["s"] > mid]
            nearest = min(stations, key=lambda x: abs(x["s"] - mid))
            hotspots.append({
                "start_m": round(s0), "end_m": round(s1), "length_m": round(s1 - s0),
                "lat": round(float(la), 6), "lon": round(float(lo), 6),
                "between": f"{before[-1]['name'] if before else 'start'} → {after[0]['name'] if after else 'end'}",
                "nearest_station": nearest["name"],
                "dist_to_station_m": round(abs(nearest["s"] - mid)),
                "median_score": round(float(g["median_score"].max()), 2),
                "repeat_rate": round(float(g["hot_frac"].max()), 2),
                "runs_covering": int(g["runs"].max()),
            })
    H = pd.DataFrame(hotspots)
    if len(H):
        H["priority"] = H["median_score"] * H["repeat_rate"]
        H = H.sort_values("priority", ascending=False).reset_index(drop=True)
        H.insert(0, "rank", np.arange(1, len(H) + 1))
    H.to_csv(os.path.join(outdir, "hotspots.csv"), index=False)

    result = {
        "runs_used": int(nruns), "files_total": len(files),
        "speed_exponent": round(b, 2), "bin_m": BIN_M,
        "stations": stations, "hotspots": H.to_dict("records"),
        "bins": B[["s_start", "median_score", "hot_frac", "runs", "lat", "lon"]].round(4).to_dict("records"),
        "line": [[round(a, 6), round(b_, 6)] for a, b_ in zip(line.lat, line.lon)],
        "runs": summary.fillna("").to_dict("records"),
        "profiles": {r: per[r].round(3).where(per[r].notna(), None).tolist() for r in per.columns},
        "profile_s": (per.index * BIN_M + BIN_M / 2).tolist(),
    }
    json.dump(result, open(os.path.join(outdir, "results.json"), "w"), default=float)
    make_profile_png(per, B, H, stations, os.path.join(outdir, "profile.png"))
    print(f"\nRuns used: {nruns}/{len(files)}  hotspots: {len(H)}")
    if len(H):
        print(H.head(15).to_string(index=False))
    return result


def make_profile_png(per, B, H, stations, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    s_km = (per.index * BIN_M + BIN_M / 2) / 1000
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 7), sharex=True,
                                   gridspec_kw={"height_ratios": [2, 1.2]})
    for r in per.columns:
        ax1.plot(s_km, per[r].values, lw=0.8, alpha=0.45)
    ax1.plot(s_km, B["median_score"].values, color="black", lw=2, label="median across runs")
    for _, h in H.iterrows() if len(H) else []:
        ax1.axvspan(h["start_m"] / 1000, h["end_m"] / 1000, color="red", alpha=0.15)
        ax1.text((h["start_m"] + h["end_m"]) / 2000, ax1.get_ylim()[1] * 0.92, f"#{h['rank']}",
                 ha="center", color="red", fontsize=9, fontweight="bold")
    ax1.set_ylabel("shake score (1 = typical)")
    ax1.legend(loc="upper left")
    ax1.set_title("E Line track roughness — every run overlaid (peaks that line up = real track features)")
    mat = per.T.values
    ax2.imshow(np.nan_to_num(mat, nan=0), aspect="auto", cmap="magma",
               extent=[s_km.min(), s_km.max(), len(per.columns) - 0.5, -0.5], vmin=0, vmax=4)
    ax2.set_yticks(range(len(per.columns)))
    ax2.set_yticklabels(per.columns, fontsize=7)
    ax2.set_ylabel("run")
    lo, hi = s_km.min(), s_km.max()
    ticks = [(x["s"] / 1000, x["name"]) for x in stations if lo - 0.2 <= x["s"] / 1000 <= hi + 0.2]
    ax2.set_xticks([t[0] for t in ticks])
    ax2.set_xticklabels([t[1] for t in ticks], rotation=40, ha="right", fontsize=8)
    ax2.set_xlim(lo, hi)
    fig.tight_layout()
    fig.savefig(path, dpi=140)
    plt.close(fig)


if __name__ == "__main__":
    folder = sys.argv[1]
    outdir = sys.argv[2] if len(sys.argv) > 2 else "trackscan_out"
    line_json = sys.argv[3] if len(sys.argv) > 3 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "eline.json")
    analyze(folder, outdir, line_json)
