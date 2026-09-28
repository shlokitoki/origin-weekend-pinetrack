"""Slide-ready figures for every finding (16:9 PNG, 2000x1125)."""
import sys, os, json, pickle
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'pipeline'))
import numpy as np, pandas as pd
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
from matplotlib.patches import FancyBboxPatch, Rectangle
from matplotlib.colors import LinearSegmentedColormap, ListedColormap, BoundaryNorm
import warnings; warnings.filterwarnings('ignore')

ROOT = os.path.dirname(os.path.abspath(__file__)); OUT = os.path.join(ROOT, 'figures'); os.makedirs(OUT, exist_ok=True)
for w in ['Regular', 'Medium', 'SemiBold', 'Bold']:   # optional: put IBM Plex Sans TTFs in ./fonts, else a default font is used
    fp = os.path.join(ROOT, 'fonts', f'IBMPlexSans-{w}.ttf')
    if os.path.exists(fp): fm.fontManager.addfont(fp)
SURF = '#fcfcfb'; INK = '#0b0b0b'; INK2 = '#52514e'; MUTED = '#8a8983'; GRID = '#e6e5e1'
S = ['#2a78d6', '#eb6834', '#1baf7a', '#eda100', '#e87ba4', '#008300', '#4a3aa7', '#e34948']
ELINE = '#5bc2e7'; ACCENT = '#0b7aa1'
CRIT = '#d03b3b'; WARN = '#fab219'; SERIOUS = '#ec835a'; GOOD = '#0ca30c'
DIV = ['#256abf', '#6da7ec', '#b7d3f6', '#e6e5e1', '#f4c1bf', '#e8807f', '#c8353a']
SEQ = ['#f4f8fd', '#cde2fb', '#9ec5f4', '#6da7ec', '#3987e5', '#256abf', '#184f95', '#0d366b']
plt.rcParams.update({'font.family': ['IBM Plex Sans', 'DejaVu Sans'], 'font.size': 12, 'text.color': INK, 'axes.edgecolor': GRID,
                     'axes.labelcolor': INK2, 'xtick.color': INK2, 'ytick.color': INK2, 'axes.facecolor': SURF,
                     'figure.facecolor': SURF, 'savefig.facecolor': SURF, 'axes.spines.top': False, 'axes.spines.right': False,
                     'axes.grid': False, 'xtick.major.size': 0, 'ytick.major.size': 0, 'axes.titleweight': 600})

D = json.load(open(os.path.join(ROOT, 'out', 'dashboard_data.json')))
ST = D['stations']; SHORT = {'Expo Park/USC': 'Expo Park/USC', 'Expo/Vermont': 'Vermont', 'Expo/Western': 'Western', 'Expo/Crenshaw': 'Crenshaw',
                             'Farmdale': 'Farmdale', 'Expo/La Brea': 'La Brea', 'La Cienega/Jefferson': 'La Cienega', 'Culver City': 'Culver City'}
TRAIN_LABEL = {k: f"{p['start']} {'eastbound' if p['dir'] == 'EB' else 'westbound'}" for k, p in D['prof'].items()}
TRAIN_COL = {str(i): S[i] for i in range(6)}
SRC_OURS = 'Source: 13 phyphox recordings on LA Metro E Line, 26 Sep 2026; LA Metro GTFS track geometry.'

def frame(title, subtitle, source=SRC_OURS, fig=None):
    fig = fig or plt.figure(figsize=(13.333, 7.5), dpi=150)
    fig.text(0.045, 0.935, title, fontsize=24, fontweight=600, color=INK, va='top')
    if subtitle: fig.text(0.045, 0.868, subtitle, fontsize=13.5, color=INK2, va='top')
    if source: fig.text(0.045, 0.03, source, fontsize=9.5, color=MUTED, va='bottom')
    return fig

def hgrid(ax, axis='y'):
    ax.grid(True, axis=axis, color=GRID, lw=1); ax.set_axisbelow(True)
    for s in ['left', 'bottom']: ax.spines[s].set_visible(False)

def chainage_axis(ax, show_stations=True, top=True):
    ax.set_xlim(9700, -60)
    if show_stations:
        for st in ST: ax.axvline(st['s'], color=MUTED, lw=0.8, alpha=0.5, zorder=0)
    ax.set_xticks([k * 1000 for k in range(10)]); ax.set_xticklabels([f'{k} km' for k in range(10)], fontsize=10)

def station_labels(ax, y=1.02):
    for st in ST:
        ha = 'right' if st['s'] < 700 else ('left' if st['s'] > 9550 else 'center')
        nm = 'USC' if st['s'] < 60 else SHORT[st['name']]
        ax.text(st['s'], y, nm, transform=ax.get_xaxis_transform(), ha=ha, va='bottom', fontsize=11, fontweight=600, color=INK)

def dot_legend(fig, x, y, items, fs=10.5):
    ax = fig.add_axes([x, y - 0.015, 0.4, 0.03]); ax.axis('off'); ax.set_xlim(0, 1); ax.set_ylim(0, 1); cx = 0.0
    for col, lab in items:
        ax.scatter([cx + 0.012], [0.5], s=70, color=INK, edgecolor=col, lw=2.2, clip_on=False)
        ax.text(cx + 0.035, 0.5, lab, va='center', fontsize=fs, color=INK2); cx += 0.035 + 0.0215 * len(lab) * fs / 10.5 + 0.03

def save(fig, name):
    fig.savefig(os.path.join(OUT, name), dpi=150); plt.close(fig); print('saved', name)

zones = D['zones']

# ---------------------------------------------------------------- 00 cover / at a glance
def f00():
    fig = frame('E Line Track Scan: every passenger as a track inspector',
                'Phones on LA Metro trains, a noise-cleaning pipeline and a model trained on real defects, turned into a repair priority list.', source=SRC_OURS + ' Beijing Subway labeled dataset (CC-BY).')
    tiles = [('2.5M', 'motion-sensor readings\nfrom 4 phones\non 6 trains'), ('3', 'rough-track zones\nconfirmed by\nrepeat trains'),
             ('2 of 6', 'trains had vibration\nlocked to wheel\nrotation'), ('0.95', 'AUC on real labeled\ndefects with\nphone-style signals'),
             ('~10', 'passes to confirm a\nnew 0.6 m/s² jolt\n(projected)')]
    n = len(tiles); x0, w, gap = 0.045, (0.91 - 0.02 * (n - 1)) / n, 0.02
    for i, (v, l) in enumerate(tiles):
        x = x0 + i * (w + gap)
        fig.patches.append(Rectangle((x, 0.40), w, 0.36, transform=fig.transFigure, facecolor='white', edgecolor=GRID, lw=1))
        fig.patches.append(Rectangle((x, 0.755), w, 0.008, transform=fig.transFigure, facecolor=ELINE, edgecolor='none'))
        fig.text(x + 0.018, 0.66, v, fontsize=44, fontweight=600, color=INK, va='center')
        fig.text(x + 0.018, 0.50, l, fontsize=12.5, color=INK2, va='center', linespacing=1.4)
    fig.text(0.045, 0.30, 'Surveyed: Expo Park/USC → Culver City, 9.6 km, both directions', fontsize=14, color=INK2)
    # mini route bar
    ax = fig.add_axes([0.045, 0.12, 0.91, 0.12]); ax.set_xlim(9700, -60); ax.set_ylim(-1, 1.6); ax.axis('off')
    ax.plot([9621, 0], [0, 0], color=ELINE, lw=7, solid_capstyle='round', zorder=1)
    for st in ST:
        ax.scatter(st['s'], 0, s=110, facecolor='white', edgecolor=INK, lw=2, zorder=3)
        ax.text(st['s'], 0.55, 'USC' if st['s'] < 60 else SHORT[st['name']], ha='right' if st['s'] < 700 else 'center', fontsize=11, color=INK)
    for z in zones:
        ax.scatter(z['s_peak'], -0.62, s=260, color=INK, zorder=4, edgecolor=CRIT if z['tier'] == 1 else WARN, lw=2.5)
        ax.text(z['s_peak'], -0.62, str(z['rank']), color='white', ha='center', va='center', fontsize=10, fontweight=600, zorder=5)
    save(fig, '00_at_a_glance.png')

# ---------------------------------------------------------------- 01 pipeline
def f01():
    fig = frame('How it works: from phone recordings to a repair list', 'Seven steps, each one removing a source of error or adding evidence.', source='')
    steps = [('Ride', '13 recordings,\n4 phones, 6 trains,\nboth directions'),
             ('Clean', 'Drop moments a\nphone was handled;\nfix orientation;\nremove braking\neffects'),
             ('Locate', 'Fuse every phone\'s\nGPS onto LA\nMetro\'s track map\n(±10 m)'),
             ('Separate', 'Split wheel\nvibration from\ntrack vibration\n(order tracking)'),
             ('Verify', 'Keep only spots\nindependent trains\nagree on (3,000-run\npermutation test)'),
             ('Cross-check', 'ML model trained\non 37k labeled\nBeijing Subway\ndefect windows'),
             ('Prioritize', 'Evidence × riders\naffected × speed ×\nnearby structures')]
    n = len(steps); x0, gap = 0.045, 0.012; w = (0.91 - gap * (n - 1)) / n; y, h = 0.36, 0.40
    for i, (t, d) in enumerate(steps):
        x = x0 + i * (w + gap)
        fig.patches.append(FancyBboxPatch((x, y), w, h, boxstyle='round,pad=0,rounding_size=0.012', transform=fig.transFigure, facecolor='white', edgecolor=GRID, lw=1.2))
        fig.text(x + 0.012, y + h - 0.04, str(i + 1), fontsize=30, fontweight=700, color=ACCENT, va='top')
        fig.text(x + 0.012, y + h - 0.15, t, fontsize=16, fontweight=600, color=INK, va='top')
        fig.text(x + 0.012, y + h - 0.21, d, fontsize=10.8, color=INK2, va='top', linespacing=1.45)
        if i < n - 1: fig.text(x + w + gap / 2, y + h / 2, '›', fontsize=22, color=MUTED, ha='center', va='center')
    fig.text(0.045, 0.24, 'Outputs', fontsize=13, fontweight=600, color=INK)
    fig.text(0.045, 0.19, 'Track condition map for both tracks  ·  ranked zone list with Street View links  ·  wheel alerts', fontsize=13, color=INK2)
    fig.text(0.045, 0.145, 'Measured detection limits  ·  code that processes a new ride in about 90 seconds', fontsize=13, color=INK2)
    save(fig, '01_pipeline.png')

# ---------------------------------------------------------------- 02 map
def f02():
    fig = frame('Seven candidate zones on 9.6 km of track; three confirmed by repeat trains',
                'Zone markers: red ring = confirmed (false-discovery rate ≤ 10%), yellow ring = probable. North is up.', source=SRC_OURS)
    ax = fig.add_axes([0.045, 0.14, 0.91, 0.66]); kx = np.cos(np.radians(34.02))
    lat = np.array([p[0] for p in D['line']]); lon = np.array([p[1] for p in D['line']])
    ax.plot(lon * kx, lat, color=ELINE, lw=8, solid_capstyle='round', solid_joinstyle='round', zorder=1)
    below = {'Expo/Vermont', 'Expo/Crenshaw', 'Expo/La Brea', 'Culver City'}
    for st in ST:
        ax.scatter(st['lon'] * kx, st['lat'], s=120, facecolor='white', edgecolor=INK, lw=2.2, zorder=3)
        ax.annotate(SHORT[st['name']], (st['lon'] * kx, st['lat']), xytext=(0, -20 if st['name'] in below else 13), textcoords='offset points',
                    ha='center', va='center', fontsize=12, color=INK2)
    offs = {1: (0, 34), 2: (0, 34), 3: (22, -34), 4: (-10, 38), 5: (0, -40), 6: (0, 34), 7: (0, 34)}
    for z in zones:
        x, y = z['lon'] * kx, z['lat']; dx, dy = offs.get(z['rank'], (0, 30))
        ax.annotate('', (x, y), xytext=(dx, dy), textcoords='offset points', arrowprops=dict(arrowstyle='-', color=INK2, lw=1))
        ax.scatter(x, y, s=40, color=INK, zorder=4)
        ax.annotate(str(z['rank']), (x, y), xytext=(dx, dy), textcoords='offset points', ha='center', va='center', fontsize=12, fontweight=600, color='white',
                    bbox=dict(boxstyle='circle,pad=0.35', facecolor=INK, edgecolor=CRIT if z['tier'] == 1 else WARN, lw=2.5), zorder=6)
    ax.set_aspect('equal'); ax.axis('off')
    # legend list
    xs = ax.get_xlim(); ys = ax.get_ylim()
    txt = '\n'.join(f"{z['rank']}  {'Confirmed' if z['tier'] == 1 else 'Probable '}  {z['where']}" for z in zones)
    fig.text(0.64, 0.80, txt, fontsize=11.5, color=INK2, va='top', linespacing=1.6)
    # scale bar 1 km
    sb = 1000 / 111320
    x0 = xs[0] + 0.001; y0 = ys[0] + 0.0008
    ax.plot([x0, x0 + sb * kx], [y0, y0], color=INK2, lw=2.5)
    ax.text(x0 + sb * kx / 2, y0 + 0.0005, '1 km', ha='center', fontsize=10.5, color=INK2)
    save(fig, '02_zone_map.png')

# ---------------------------------------------------------------- 03 condition strip + height
def f03():
    fig = frame('Where the ride is consistently rough, on each track',
                'Each cell is 20 m of track: vibration vs. normal track at the same speed, averaged over all trains in that direction. Culver City is on the left.')
    ax = fig.add_axes([0.13, 0.43, 0.83, 0.33])
    cmap = ListedColormap(DIV); bounds = [-9, -1, -0.5, -0.2, 0.2, 0.6, 1.1, 9]; norm = BoundaryNorm(bounds, cmap.N)
    for row, d, lab in [(1, 'WB', 'Westbound ←\n(north track)'), (0, 'EB', 'Eastbound →\n(south track)')]:
        for sg in D['segs'][d]:
            c = '#f3f3f1' if (sg['ev'] is None or sg['M'] is None) else cmap(norm(sg['M']))
            ax.add_patch(Rectangle((sg['s'] - 10, row + 0.08), 20, 0.84, facecolor=c, edgecolor='none'))
        ax.text(1.0 - 1.02, row + 0.5, lab, transform=ax.get_yaxis_transform(), ha='right', va='center', fontsize=12, color=INK2)
    ax.set_ylim(-0.15, 2.9); ax.set_yticks([]); chainage_axis(ax); station_labels(ax, y=0.985)
    for sp in ['left', 'bottom']: ax.spines[sp].set_visible(False)
    ax.set_xticklabels([])
    for z in zones:
        col = CRIT if z['tier'] == 1 else WARN
        ax.plot([z['s_to'] + 10, z['s_to'] + 10, z['s_from'] - 10, z['s_from'] - 10], [2.02, 2.12, 2.12, 2.02], color=INK, lw=1.3)
        xc = (z['s_from'] + z['s_to']) / 2
        ax.text(xc, 2.45, str(z['rank']), ha='center', va='center', fontsize=11, fontweight=600, color='white',
                bbox=dict(boxstyle='circle,pad=0.32', facecolor=INK, edgecolor=col, lw=2.5))
    # colour legend
    lax = fig.add_axes([0.13, 0.355, 0.30, 0.025])
    for i, c in enumerate(DIV): lax.add_patch(Rectangle((i, 0), 0.94, 1, facecolor=c))
    lax.set_xlim(0, 7); lax.set_ylim(0, 1); lax.axis('off')
    fig.text(0.13, 0.33, 'smoother', fontsize=10.5, color=INK2, va='top'); fig.text(0.43, 0.33, 'rougher', fontsize=10.5, color=INK2, va='top', ha='right')
    fig.text(0.445, 0.366, 'vs. normal track   ·   ', fontsize=10.5, color=INK2, va='center')
    dot_legend(fig, 0.58, 0.367, [(CRIT, 'confirmed zone'), (WARN, 'probable zone')])
    # height profile
    hx = fig.add_axes([0.13, 0.09, 0.83, 0.20])
    s = np.array(D['elev_s']); e = np.array([np.nan if v is None else v for v in D['elev']])
    hx.fill_between(s, -3, e, color=ELINE, alpha=0.25, lw=0); hx.plot(s, e, color=ACCENT, lw=2)
    chainage_axis(hx); hx.set_ylim(-3, 15); hx.set_yticks([0, 5, 10]); hx.set_yticklabels(['0 m', '5 m', '10 m'], fontsize=10); hgrid(hx)
    for sx, v, t in [(6480, 8.6, 'La Brea aerial'), (8080, 9.0, 'La Cienega aerial'), (9380, 12.3, 'Culver City aerial')]:
        hx.text(sx, v + 1.2, t, ha='center', fontsize=10.5, color=INK2)
    hx.text(-0.055, 0.5, 'Track height\nfrom phone tilt', transform=hx.transAxes, ha='right', va='center', fontsize=11.5, color=INK2)
    hx.text(1.0, -0.28, 'distance from Expo Park/USC', transform=hx.transAxes, ha='right', fontsize=10, color=MUTED)
    save(fig, '03_condition_strip.png')

# ---------------------------------------------------------------- 04 zone traces
def f04():
    fig = frame('Independent trains agree at the two confirmed zones',
                'Roughness vs. normal track (σ) for each train, ±700 m around the zone. Coloured lines = trains (median of phones aboard); black = average.')
    rows = [z for z in zones if z['rank'] in (1, 2)]
    for r, z in enumerate(rows):
        for c, d in enumerate(['WB', 'EB']):
            ax = fig.add_axes([0.07 + c * 0.47, 0.50 - r * 0.36, 0.42, 0.27])
            s0, s1 = z['s_peak'] - 700, z['s_peak'] + 700
            ax.axvspan(z['s_from'] - 15, z['s_to'] + 15, color=CRIT, alpha=0.10, lw=0)
            trains = [(k, p) for k, p in D['prof'].items() if p['dir'] == d]
            i0, i1 = int(max(0, s0 // 20)), int(min(482, s1 // 20))
            xs = np.arange(i0, i1 + 1) * 20 + 10
            M = np.array([[np.nan if p['vals'][i] is None else p['vals'][i] for i in range(i0, i1 + 1)] for k, p in trains])
            for (k, p), row in zip(trains, M): ax.plot(xs, np.clip(row, -2.5, 3.5), color=TRAIN_COL[k], lw=2, alpha=0.9)
            cnt = np.sum(~np.isnan(M), 0); mean = np.where(cnt >= 2, np.nanmean(M, 0), np.nan)
            ax.plot(xs, mean, color=INK, lw=2.8)
            ax.set_xlim(s1, s0); ax.set_ylim(-2.5, 3.5); ax.set_yticks([-2, 0, 2]); hgrid(ax)
            ax.set_xticks([z['s_peak'] + o for o in (600, 300, 0, -300, -600)])
            ax.set_xticklabels(['600 m W', '300 m W', 'zone', '300 m E', '600 m E'], fontsize=9.5)
            for st in ST:
                if s0 < st['s'] < s1: ax.axvline(st['s'], color=MUTED, lw=0.8); ax.text(st['s'], 3.3, ' ' + SHORT[st['name']], fontsize=9.5, color=INK2, va='top')
            ttl = f"Zone {z['rank']} · {z['where']} · {'westbound' if d == 'WB' else 'eastbound'} ({len(trains)} trains)"
            ax.set_title(ttl, loc='left', fontsize=12, color=INK, pad=6)
    # legend
    hs = [plt.Line2D([], [], color=TRAIN_COL[k], lw=2.5) for k in D['prof']] + [plt.Line2D([], [], color=INK, lw=3)]
    ls = [TRAIN_LABEL[k] for k in D['prof']] + ['average of trains']
    fig.legend(hs, ls, loc='lower center', bbox_to_anchor=(0.5, 0.055), ncol=7, frameon=False, fontsize=10.5)
    save(fig, '04_zone_train_traces.png')

# ---------------------------------------------------------------- 05 repeatability
def f05():
    fig = frame('Phones on one train agree closely; the track signal repeats across trains',
                'Correlation of 50 m roughness profiles between pairs of recordings.')
    ax = fig.add_axes([0.30, 0.22, 0.62, 0.52])
    rows = [('Phones on the same train', D['same_train_r'], 'handling noise removed'),
            ('Different trains, same track', D['rep']['z_comp|50']['same'], 'the repeatable track signal'),
            ('Different trains, opposite track', D['rep']['z_comp|50']['opp'], 'each direction has its own rails')]
    for i, (lab, v, note) in enumerate(rows):
        y = len(rows) - 1 - i
        ax.barh(y, v, height=0.42, color=S[0])
        ax.text(v + 0.015, y, f'{v:.2f}', va='center', fontsize=15, fontweight=600, color=INK)
        ax.text(-0.02, y + 0.07, lab, va='center', ha='right', fontsize=14, color=INK, transform=ax.get_yaxis_transform())
        ax.text(-0.02, y - 0.17, note, va='center', ha='right', fontsize=11, color=MUTED, transform=ax.get_yaxis_transform())
    ax.set_xlim(0, 1); ax.set_yticks([]); ax.set_xticks([0, 0.25, 0.5, 0.75, 1]); hgrid(ax, 'x')
    fig.text(0.30, 0.14, 'Same-track agreement beats opposite-track agreement: 1.5× overall and 2.5× for sharp impacts (0.30 vs 0.12).\nEach direction runs on its own rails, so this is the signature of real track condition.', fontsize=12, color=INK2, va='top', linespacing=1.5)
    save(fig, '05_repeatability.png')

# ---------------------------------------------------------------- 06 wheel spectrogram
def f06(sigs):
    from wheel import spectra
    fig = frame('On one train, the vibration tracks wheel rotation exactly',
                'Vertical vibration by frequency and train speed. Same phone, two different trains. Dashed line: one wheel turn (speed ÷ π × 0.711 m wheel).')
    names = {'normal': '3_2026-09-26_11-43-20', 'hot': 'track_brooke_3_2026-09-26_10-49-40'}
    ttl = {'normal': '11:25 eastbound train: no wheel signature', 'hot': '10:30 westbound train: strong wheel signature'}
    cmap = LinearSegmentedColormap.from_list('seq', SEQ)
    for c, key in enumerate(['normal', 'hot']):
        sig = next(s for s in sigs.values() if s['name'] == names[key])
        f, tt, P, v, hand, sc = spectra(sig)
        sel = (v > 2) & ~hand
        vb = np.arange(2, 26.5, 0.5); idx = np.digitize(v[sel], vb) - 1
        H = np.full((len(f), len(vb) - 1), np.nan)
        for j in range(len(vb) - 1):
            m = idx == j
            if m.sum() >= 1: H[:, j] = np.log10(np.median(P[:, sel][:, m], axis=1) + 1e-9)
        ax = fig.add_axes([0.06 + c * 0.47, 0.17, 0.42, 0.60])
        ax.pcolormesh((vb[:-1] + vb[1:]) / 2, f, H, cmap=cmap, vmin=-6.3, vmax=-2.8, shading='nearest')
        vv = np.linspace(2, 26, 50); ax.plot(vv, vv / (np.pi * 0.711), color=CRIT, lw=1.6, ls=(0, (5, 3)))
        ax.set_ylim(0, 30); ax.set_xlim(2, 26); ax.set_xlabel('train speed (m/s)'); ax.set_ylabel('frequency (Hz)' if c == 0 else '')
        ax.set_title(ttl[key], loc='left', fontsize=13.5, color=INK, pad=8)
        for sp in ['left', 'bottom']: ax.spines[sp].set_visible(False)
        ax.text(25.5, 25.5 / (np.pi * 0.711) - 2.2, 'wheel turn', color=INK, fontsize=10.5, ha='right', bbox=dict(facecolor='white', alpha=0.85, edgecolor='none', pad=2))
        ax.text(3, 22.3, 'onboard equipment tone (same frequency at every speed)', fontsize=10, color=INK, bbox=dict(facecolor='white', alpha=0.85, edgecolor='none', pad=2))
        if key == 'hot': ax.text(17.5, 2 * 17.5 / (np.pi * 0.711) + 1.2, 'second harmonic', fontsize=10, color=INK, ha='right', bbox=dict(facecolor='white', alpha=0.85, edgecolor='none', pad=2))
    fig.text(0.06, 0.09, 'Lighter = less energy, darker = more. The dark band hugging the dashed line on the right is vibration once per wheel revolution.', fontsize=11.5, color=INK2)
    save(fig, '06_wheel_spectrogram.png')

# ---------------------------------------------------------------- 07 wheel dots
def f07():
    fig = frame('Two of six trains carried vibration locked to wheel rotation',
                'Energy at the wheel-rotation frequency ÷ energy in neighbouring bands, per phone. 1× = no wheel signature. Log scale.',
                source=SRC_OURS + ' P3010 wheel diameter: Kinki Sharyo P3010 (Wikipedia).')
    ax = fig.add_axes([0.18, 0.20, 0.47, 0.56])
    W = pd.DataFrame(D['wheel']); tstart = W.groupby('trip').start.min(); order = tstart.sort_values().index.tolist()
    for i, t in enumerate(order):
        g = W[W.trip == t]; y = len(order) - 1 - i; med = g.ratio.median(); hot = med > 3
        ax.scatter(g.ratio.clip(lower=0.55), [y] * len(g), s=110, color=SERIOUS if hot else MUTED, edgecolor=SURF, lw=2, zorder=3)
        ax.text(-0.02, y, f"{tstart[t]} {'eastbound' if g.dir.iloc[0] == 'EB' else 'westbound'}", transform=ax.get_yaxis_transform(), ha='right', va='center', fontsize=13)
        ax.text(1.02, y, f'{med:.1f}×' + ('  wheel alert' if hot else ''), transform=ax.get_yaxis_transform(), va='center', fontsize=13, fontweight=600 if hot else 400, color=INK)
    ax.set_xscale('log'); ax.set_xlim(0.5, 40); ax.set_xticks([0.5, 1, 3, 10, 30]); ax.set_xticklabels(['0.5×', '1×', '3×', '10×', '30×'])
    ax.axvline(3, color=INK2, lw=1, ls=(0, (3, 3))); ax.text(3.15, len(order) - 0.45, 'clear signature', fontsize=10.5, color=INK2)
    ax.set_yticks([]); ax.set_ylim(-0.6, len(order) - 0.3); hgrid(ax, 'x')
    # diameter panel
    fig.text(0.79, 0.72, 'Wheel size check', fontsize=15, fontweight=600, color=INK)
    fig.text(0.79, 0.66, 'Solving for the wheel diameter\nthat best fits the signal:', fontsize=12, color=INK2, va='top', linespacing=1.4)
    fig.text(0.79, 0.54, '705–708 mm', fontsize=30, fontweight=600, color=INK)
    fig.text(0.79, 0.49, 'from 5 phones on the two trains', fontsize=11.5, color=INK2)
    fig.text(0.79, 0.40, '711 mm', fontsize=30, fontweight=600, color=INK2)
    fig.text(0.79, 0.35, 'P3010 wheel when new (28 in)', fontsize=11.5, color=INK2)
    fig.text(0.79, 0.25, 'Within 1% of spec, and just under,\nas worn wheels should be. Energy is\nmostly once per turn: out-of-round\nor eccentric, not a sharp flat spot.', fontsize=11.5, color=INK2, va='top', linespacing=1.45)
    save(fig, '07_wheel_ratio.png')

# ---------------------------------------------------------------- 08 handling removal
def f08(sigs):
    from signals import bp
    best = None
    for sig in sigs.values():
        h = sig['hand']; ed = np.flatnonzero(np.diff(np.r_[0, h.astype(int), 0]))
        glp = bp(sig['a'], None, 1.0, order=2); gdir = glp / np.linalg.norm(glp, axis=1, keepdims=True)
        wmag = np.linalg.norm(bp(sig['w'], None, 2.0), axis=1)
        for i0, i1 in zip(ed[::2], ed[1::2]):
            if i1 - i0 > 25 * 100 or i0 < 35 * 100 or i1 > len(h) - 35 * 100: continue
            if np.median(sig['v'][i0:i1]) < 6: continue
            ref = np.median(gdir[i0 - 3000:i0 - 500], axis=0); ref /= np.linalg.norm(ref)
            tilt = np.degrees(np.arccos(np.clip(gdir[i0:i1] @ ref, -1, 1))).max()
            score = min(tilt, 60) + 10 * min(wmag[i0:i1].max(), 3)
            if best is None or score > best[0]: best = (score, sig, i0, i1, gdir, wmag)
    _, sig, i0, i1, gdir, wmag = best
    c = (i0 + i1) // 2; a, b = c - 30 * 100, c + 22 * 100
    ref = np.median(gdir[a:i0 - 300], axis=0); ref /= np.linalg.norm(ref)
    tilt = np.degrees(np.arccos(np.clip(gdir[a:b] @ ref, -1, 1)))
    fig = frame('We automatically remove moments when someone touches a phone',
                'Part of one recording on a moving train. Shaded: flagged as handling (fast tilt change or rotation > 0.3 rad/s, ±3 s) and excluded.')
    ax1 = fig.add_axes([0.08, 0.50, 0.87, 0.27]); ax2 = fig.add_axes([0.08, 0.16, 0.87, 0.27], sharex=ax1)
    tt = (np.arange(a, b) - a) / 100.0
    ax1.plot(tt, sig['av'][a:b], color=S[0], lw=0.8); ax1.set_ylabel('vertical accel. (m/s²)')
    ax2.plot(tt, tilt, color=S[6], lw=1.6); ax2.set_ylabel('phone tilt (degrees)')
    hh = sig['hand'][a:b]; ed = np.flatnonzero(np.diff(np.r_[0, hh.astype(int), 0]))
    for ax in (ax1, ax2):
        for j0, j1 in zip(ed[::2], ed[1::2]): ax.axvspan(tt[j0], tt[min(j1, len(tt) - 1)], color=SERIOUS, alpha=0.2, lw=0)
        hgrid(ax)
    j0 = ed[0]; ax1.text(tt[j0] + 0.4, 0.93, 'removed: phone handled', transform=ax1.get_xaxis_transform(), fontsize=11, color=INK, fontweight=600, va='top')
    ax2.set_xlabel('seconds'); plt.setp(ax1.get_xticklabels(), visible=False)
    fig.text(0.08, 0.075, 'Across all 13 recordings, 2–13% of the data was removed this way. Afterwards, phones on the same train agreed at r = 0.85.', fontsize=12, color=INK2)
    print('handling example from', sig['name'], 'max tilt', round(float(tilt.max()), 1))
    save(fig, '08_handling_removed.png')

# ---------------------------------------------------------------- 09 elevation
def f09():
    fig = frame('The phones mapped the line\'s vertical profile from tilt alone',
                'Relative track height reconstructed from phone tilt minus the train\'s own acceleration. The three elevated stations appear as humps.')
    ax = fig.add_axes([0.07, 0.17, 0.88, 0.56])
    s = np.array(D['elev_s']); e = np.array([np.nan if v is None else v for v in D['elev']])
    ax.fill_between(s, -3, e, color=ELINE, alpha=0.25, lw=0); ax.plot(s, e, color=ACCENT, lw=2.4)
    chainage_axis(ax); station_labels(ax); ax.set_ylim(-3, 15); ax.set_yticks([0, 5, 10]); ax.set_yticklabels(['0 m', '5 m', '10 m']); hgrid(ax)
    for sx, v, tx, ty in [(6480, 8.6, 'La Brea\naerial station', 11.8), (8070, 9.0, 'La Cienega/Jefferson\naerial station', 12.2), (9300, 12.2, 'Culver City\naerial station', 3.0)]:
        ax.annotate(tx, (sx, v if ty > v else v - 0.6), xytext=(sx, ty), ha='center', fontsize=11, color=INK, arrowprops=dict(arrowstyle='-', color=INK2, lw=1))
    ax.axvline(D['ramp_start'], color=INK, lw=1); ax.text(D['ramp_start'] - 30, -2.4, 'climb starts\n7,810 m', fontsize=9.5, color=INK2, ha='left')
    z2 = next(z for z in zones if z['rank'] == 2); ax.axvspan(z2['s_from'] - 10, z2['s_to'] + 10, color=CRIT, alpha=0.12, lw=0)
    ax.text((z2['s_from'] + z2['s_to']) / 2, 13.6, 'zone 2', ha='center', fontsize=10.5, color=CRIT, fontweight=600)
    fig.text(0.07, 0.085, 'Aerial status of La Brea, La Cienega/Jefferson and Culver City stations confirmed on each station\'s Wikipedia page.', fontsize=11, color=INK2)
    save(fig, '09_elevation_profile.png')

# ---------------------------------------------------------------- 10 Beijing ROC
def f10():
    from beijing import window_stats, SpeedNorm, PHONE_FEATS
    from sklearn.ensemble import HistGradientBoostingClassifier
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import roc_curve, roc_auc_score
    tr = pd.read_pickle(os.path.join(ROOT, 'ext', 'bj_train.pkl')); te = pd.read_pickle(os.path.join(ROOT, 'ext', 'bj_test.pkl'))
    Ftr, Fte = window_stats(tr), window_stats(te); Ftr = Ftr.loc[~Ftr.drop(columns=['label']).round(6).duplicated()]
    full = [c for c in Ftr.columns if c not in ('label', 'vel', 'train')]
    sn = SpeedNorm().fit(Ftr, PHONE_FEATS); Ztr, Zte = sn.transform(Ftr), sn.transform(Fte); y = (Fte.label.values > 0)
    hgb = lambda: HistGradientBoostingClassifier(max_iter=300, learning_rate=0.06, max_leaf_nodes=31, l2_regularization=1.0, random_state=0)
    models = [('All 5 sensor channels, boosted trees', hgb(), Ftr[full], Fte[full]),
              ('Phone-style signals, boosted trees (used on our runs)', hgb(), Ztr, Zte),
              ('Phone-style signals, logistic regression', LogisticRegression(max_iter=2000, C=0.5), Ztr, Zte),
              ('Vertical shaking only, logistic regression', LogisticRegression(max_iter=2000), Ztr[['z_v_std', 'z_v_max']], Zte[['z_v_std', 'z_v_max']])]
    fig = frame('Trained on real labeled defects, phone-style signals catch 80% of them',
                'ROC curves on the Beijing Subway held-out test set: 3,332 windows of 20 m, 197 with inspection-confirmed defects.',
                source='Source: Beijing Subway Line 1 car-body vibration dataset (Wang et al. 2022, 2023; CC-BY), github.com/Elscip/scidata_jrrt_1. 77% duplicate training windows removed.')
    ax = fig.add_axes([0.08, 0.14, 0.45, 0.66])
    cols = [S[6], S[0], S[2], S[3]]; lws = [2, 3, 2, 2]
    for (name, m, Xtr, Xte), c, lw in zip(models, cols, lws):
        m.fit(Xtr, Ftr.label); p = m.predict_proba(Xte)[:, 1:].sum(1); fpr, tpr, _ = roc_curve(y, p); auc = roc_auc_score(y, p)
        ax.plot(fpr, tpr, color=c, lw=lw, label=f'{name}  ·  AUC {auc:.2f}')
        if 'used on our runs' in name:
            thr = np.quantile(p[~y], 0.95); rec = (p[y] > thr).mean()
            ax.scatter([0.05], [rec], s=90, color=c, edgecolor=SURF, lw=2, zorder=5)
            ax.annotate(f'5% false alarms → {rec*100:.0f}% of defects caught', (0.05, rec), xytext=(0.18, rec - 0.08), fontsize=11, color=INK,
                        arrowprops=dict(arrowstyle='-', color=INK2, lw=1))
    ax.plot([0, 1], [0, 1], color=GRID, lw=1.2)
    ax.set_xlim(0, 1); ax.set_ylim(0, 1.01); ax.set_xlabel('false-alarm rate (normal track flagged)'); ax.set_ylabel('share of real defects caught'); hgrid(ax, 'both')
    h, l = ax.get_legend_handles_labels(); fig.legend(h, l, loc='lower left', bbox_to_anchor=(0.595, 0.15), fontsize=11, frameon=False, title='Model  ·  AUC (any defect)', title_fontsize=11.5, alignment='left')
    fig.text(0.60, 0.74, 'What this shows', fontsize=15, fontweight=600, color=INK)
    fig.text(0.60, 0.70, 'Car-body vibration, the kind a phone on the\nfloor feels, really does reveal track defects.\n\nSevere defects are easiest: 97% caught at\nthe same 5% false-alarm rate (AUC 0.98).\n\nVertical shaking alone carries most of the\nsignal (AUC 0.90).',
             fontsize=12.5, color=INK2, va='top', linespacing=1.45)
    save(fig, '10_beijing_roc.png')

# ---------------------------------------------------------------- 11 cross-check along line
def f11():
    fig = frame('A model trained in Beijing independently flags the same spots',
                'Defect-model probability for every 20 m of E Line track (average over trains). Shaded: zones found by the repeat-train test.')
    for r, (d, lab) in enumerate([('WB', 'Westbound track'), ('EB', 'Eastbound track')]):
        ax = fig.add_axes([0.07, 0.49 - r * 0.33, 0.88, 0.25])
        sg = [x for x in D['segs'][d] if x['pm'] is not None and x['ev'] is not None]
        s = np.array([x['s'] for x in sg]); p = np.array([x['pm'] for x in sg])
        for z in zones:
            ax.axvspan(z['s_from'] - 15, z['s_to'] + 15, color=CRIT if z['tier'] == 1 else WARN, alpha=0.16, lw=0)
            if r == 0: ax.text((z['s_from'] + z['s_to']) / 2, 1.04, str(z['rank']), ha='center', fontsize=11, fontweight=600, color=INK, transform=ax.get_xaxis_transform())
        ax.fill_between(s, 0, p, color=S[0], alpha=0.12, lw=0, step='mid'); ax.step(s, p, where='mid', color=S[0], lw=1.4)
        chainage_axis(ax); ax.set_ylim(0, 1); ax.set_yticks([0, 0.5, 1]); ax.set_yticklabels(['0%', '50%', '100%']); hgrid(ax)
        ax.text(0.005, 0.86, lab, transform=ax.transAxes, fontsize=12.5, fontweight=600, color=INK)
        if r == 0: station_labels(ax, y=1.12)
        if r == 0: ax.set_xticklabels([])
    fig.text(0.07, 0.10, 'All three statistically confirmed zones fall in the top 1–3% of the line by this model, which was never tuned on E Line data.', fontsize=11.5, color=INK2)
    fig.text(0.07, 0.07, 'Rank correlation with our roughness index: 0.56–0.70. Both use related vibration measures, so this is corroboration rather than proof.', fontsize=11.5, color=INK2)
    save(fig, '11_model_crosscheck.png')

# ---------------------------------------------------------------- 12 detection power
def f12():
    fig = frame('Big jolts are caught right away; subtle ones need more passes',
                'Left: fake defects planted in the raw data at 24 random spots. Right: projected passes needed with a phone on every train.')
    inj = {r['amp']: r['det'] for r in D['inj']}; pw = {p['amp']: p['passes'] for p in D['power']}
    amps = [0.15, 0.3, 0.6, 1.2]; labels = ['0.15', '0.3', '0.6', '1.2']
    ax = fig.add_axes([0.07, 0.17, 0.38, 0.56])
    vals = [inj[a] * 100 for a in amps]
    bars = ax.bar(range(4), vals, width=0.5, color=S[0])
    for i, v in enumerate(vals): ax.text(i, v + 2, f'{v:.0f}%', ha='center', fontsize=14, fontweight=600, color=INK)
    ax.set_xticks(range(4)); ax.set_xticklabels([f'{l} m/s²' for l in labels]); ax.set_ylim(0, 100); ax.set_yticks([0, 25, 50, 75, 100]); ax.set_yticklabels(['0%', '25%', '50%', '75%', '100%']); hgrid(ax)
    ax.set_title('Found today (4 trains)', loc='left', fontsize=13.5, pad=10); ax.set_xlabel('peak car-body jolt of planted defect')
    ax2 = fig.add_axes([0.56, 0.17, 0.40, 0.56])
    amps2 = [0.15, 0.3, 0.6, 1.2, 2.4]; pv = [max(1, int(np.ceil(pw[a]))) for a in amps2]
    ax2.barh(range(5)[::-1], pv, height=0.5, color=S[0])
    for i, (a, v) in enumerate(zip(amps2, pv)):
        hrs = v * 8 / 60; tlab = f'{int(max(8, round(hrs * 60 / 8) * 8))} min' if hrs < 1 else (f'{hrs:.1f} h' if hrs < 24 else f'{hrs/24:.1f} days')
        ax2.text(v + 3, 4 - i, f"{v} pass{'es' if v > 1 else ''}  ·  {tlab}", va='center', fontsize=12.5, color=INK)
    ax2.set_yticks(range(5)[::-1]); ax2.set_yticklabels([f'{a} m/s²' for a in amps2]); ax2.set_xlim(0, 260); hgrid(ax2, 'x')
    ax2.set_title('Passes needed to confirm (time at 8-min headway)', loc='left', fontsize=13.5, pad=10); ax2.set_xlabel('train passes')
    fig.text(0.07, 0.085, 'Projection assumes a stable baseline from earlier days and independent passes. Normal vertical vibration at speed is ~0.15–0.25 m/s².', fontsize=11, color=INK2)
    save(fig, '12_detection_power.png')

# ---------------------------------------------------------------- 13 reliability curve
def f13():
    fig = frame('More riders, sharper results', 'How reliably the line\'s rough-spot ranking would reproduce, vs. number of train passes per direction (from measured per-pass agreement r = 0.30).')
    ax = fig.add_axes([0.08, 0.16, 0.86, 0.58]); r = 0.30
    n = np.logspace(0, 2, 200); ax.plot(n, n * r / (1 + (n - 1) * r), color=S[0], lw=3)
    for N, lab in [(2, 'westbound today'), (4, 'eastbound today'), (20, 'goal: 20 passes')]:
        v = N * r / (1 + (N - 1) * r); ax.scatter([N], [v], s=110, color=S[0], edgecolor=SURF, lw=2.5, zorder=5)
        ax.annotate(f'{lab}  ·  {v:.2f}', (N, v), xytext=(10, -22), textcoords='offset points', fontsize=12.5, fontweight=600, color=INK)
    ax.set_xscale('log'); ax.set_xticks([1, 2, 4, 10, 20, 50, 100]); ax.set_xticklabels(['1', '2', '4', '10', '20', '50', '100'])
    ax.set_ylim(0, 1.02); ax.set_yticks([0, 0.25, 0.5, 0.75, 1]); ax.set_xlabel('train passes per direction'); ax.set_ylabel('ranking reliability'); hgrid(ax, 'both')
    save(fig, '13_reliability_vs_passes.png')

# ---------------------------------------------------------------- 14 priority
def f14():
    fig = frame('Priority = evidence × consequence', 'Evidence: agreement between trains + defect model. Consequence: riders crossing the spot, train speed, nearby ramps or aerial structures.',
                source=SRC_OURS + ' Riders modeled from FY2025 station boardings and 54,006 weekday E Line riders (Mar 2026).')
    ax = fig.add_axes([0.08, 0.15, 0.55, 0.60])
    ev = np.linspace(0.3, 0.85, 200)
    for pr in [0.3, 0.4, 0.5]:
        ax.plot(ev, pr / ev, color=GRID, lw=1.2); ax.text(pr / 0.795, 0.797, f'priority {pr:.1f}', fontsize=9.5, color=MUTED, va='bottom', ha='center')
    offs = {1: (24, 14), 2: (-22, 16)}
    for z in zones:
        cons = z['priority'] / z['evidence']; col = CRIT if z['tier'] == 1 else WARN
        dx, dy = offs.get(z['rank'], (0, 22))
        ax.scatter(z['evidence'], cons, s=36, color=INK, zorder=4)
        ax.annotate(str(z['rank']), (z['evidence'], cons), xytext=(dx, dy), textcoords='offset points', ha='center', va='center', fontsize=12, fontweight=600, color='white',
                    bbox=dict(boxstyle='circle,pad=0.35', facecolor=INK, edgecolor=col, lw=2.5), arrowprops=dict(arrowstyle='-', color=INK2, lw=1), zorder=5)
    ax.set_xlim(0.35, 0.85); ax.set_ylim(0.44, 0.82); ax.set_xlabel('condition evidence →'); ax.set_ylabel('consequence of failure →'); hgrid(ax, 'both')
    ranked = sorted(zones, key=lambda z: -z['priority'])
    fig.text(0.68, 0.74, 'Repair order', fontsize=15, fontweight=600, color=INK)
    for i, z in enumerate(ranked):
        y = 0.68 - i * 0.07
        fig.text(0.68, y, f"{i+1}.", fontsize=12.5, color=MUTED)
        fig.text(0.70, y, f"Zone {z['rank']}", fontsize=12.5, fontweight=600, color=INK)
        fig.text(0.765, y, z['where'], fontsize=11.5, color=INK2)
        fig.patches.append(Rectangle((0.70, y - 0.018), 0.22 * z['priority'] / ranked[0]['priority'], 0.009, transform=fig.transFigure, facecolor=S[0]))
    dot_legend(fig, 0.68, 0.15, [(CRIT, 'confirmed zone'), (WARN, 'probable zone')], fs=11)
    save(fig, '14_priority.png')

# ---------------------------------------------------------------- 15 cost
def f15():
    fig = frame('Catching a broken rail early costs 350–700× less',
                'Average cost per broken rail: found in service vs. causing a derailment (US Class I freight railroads, 2003–06).',
                source='Source: Schafer & Barkan (2008), "A prediction model for broken rails and an analysis of their economic impact", AREMA; RailTEC, University of Illinois.')
    ax = fig.add_axes([0.28, 0.24, 0.64, 0.46])
    vals = [1500, 525400]; labs = ['Found during inspection\n(repair, $745–1,500)', 'Caused a derailment\n(track + equipment damage)']
    ax.barh([1, 0], vals, height=0.46, color=[GOOD, CRIT])
    ax.text(1500 + 6000, 1, '$1,500', va='center', fontsize=17, fontweight=600, color=INK)
    ax.text(525400 - 8000, 0, '$525,400', va='center', ha='right', fontsize=17, fontweight=600, color='white')
    for y, l in zip([1, 0], labs): ax.text(-0.02, y, l, transform=ax.get_yaxis_transform(), ha='right', va='center', fontsize=13.5, color=INK, linespacing=1.4)
    ax.set_yticks([]); ax.set_xlim(0, 560000); ax.set_xticks([0, 100000, 200000, 300000, 400000, 500000]); ax.set_xticklabels(['$0', '$100k', '$200k', '$300k', '$400k', '$500k']); hgrid(ax, 'x')
    fig.text(0.28, 0.14, 'Early detection turns a potential derailment into a routine repair. That gap is the business case for continuous monitoring.', fontsize=12.5, color=INK2)
    save(fig, '15_cost_early_vs_late.png')

if __name__ == '__main__':
    which = sys.argv[1:] or ['all']
    sigs = None
    if any(w in which for w in ['all', '06', '08']): sigs = pickle.load(open(os.path.join(ROOT, 'out', 'sigs.pkl'), 'rb'))
    fns = {'00': f00, '01': f01, '02': f02, '03': f03, '04': f04, '05': f05, '06': lambda: f06(sigs), '07': f07, '08': lambda: f08(sigs),
           '09': f09, '10': f10, '11': f11, '12': f12, '13': f13, '14': f14, '15': f15}
    for k, fn in fns.items():
        if 'all' in which or k in which: fn()
