# E Line Track Scan: phone-based track and wheel monitoring

Turns phyphox recordings (accelerometer + gyroscope + GPS) from phones riding LA Metro's E Line into:

1. **Rough-track zones** that repeat across independent trains, with a permutation significance test
2. **Wheel-defect signatures** (vibration locked to wheel rotation, found by order tracking)
3. **A defect-likelihood score** from a model trained on real labeled defects (Beijing Subway, CC-BY)
4. **A repair priority** = condition evidence × consequence (riders, speed, structures)
5. **Detection limits**, measured by planting synthetic defects in the raw data

## Quick start

```bash
pip install -r requirements.txt
python pipeline/fetch_external.py                   # LA Metro GTFS + Beijing dataset (both on GitHub)
python pipeline/run_all.py --xlsx-dir /path/to/phyphox_exports   # stage 1, about 1-2 min
python pipeline/stage2.py                           # defect model, priority, zones -> out/*.csv
python pipeline/run_injection.py                    # optional: detection-limit test (~4 min)
python make_figures.py                              # slide-ready PNGs -> figures/ (needs out/dashboard_data.json)
```

Export each phyphox experiment as **Excel** (sheets: Accelerometer, Gyroscope, Location, Metadata Time, Metadata Device).
Phones on the same train are grouped automatically by recording time. Add new phone names to `PHONE` in `pipeline/load.py`.

## Outputs (`out/`)

| File | What it is |
|---|---|
| `hotspot_zones.csv` | Ranked zones: location, tier (1 = confirmed at FDR ≤ 10%), trains agreeing, q-value, defect-model probability, speed, riders, priority |
| `segments_20m.csv` | Every 20 m of track, per direction: roughness index, evidence, model probability, grade, speed, riders, priority, lat/lon |
| `wheel_by_recording.csv` | Wheel-order vibration ratio and fitted wheel diameter per recording |
| `beijing_results.csv` | Defect-classifier scores on the Beijing held-out test set |

## How it works

| Step | File | Idea |
|---|---|---|
| Load | `load.py` | Absolute timestamps from phyphox metadata. Drops short resumed segments after a pause |
| Position | `geo.py`, `position.py` | GPS projected onto LA Metro's GTFS track geometry. All phones on a train fused with a Kalman/RTS smoother, so a phone with bad GPS borrows its neighbours' fixes |
| Signals | `signals.py` | Gravity held constant per still stretch gives true vertical. The train's own speed changes give the forward axis. Handling is flagged by fast tilt changes or rotation above 0.3 rad/s (±3 s) |
| Wheels | `wheel.py` | Order tracking at f = v / (π·D). Fits D. Ratio of energy at the wheel order to neighbouring bands |
| Features | `features2.py`, `features.py` | STFT with wheel orders (1–4×) and onboard tones (19.5 and 29.3 Hz) masked. Bands: body 0.7–3 Hz, structural 6–20 Hz, impact 20–45 Hz, peak, horizontal, roll/pitch. 5 m bins. Log-ratio to the same recording's typical value at that speed |
| Traction | `run_all.py` | Regresses out forward acceleration and braking per recording |
| Hotspots | `hotspots.py` | Median over phones per train, then mean over trains per direction. 3,000 circular-shift permutations. Benjamini–Hochberg FDR plus a line-wide max test |
| Defect model | `beijing.py`, `transfer.py` | Gradient boosting on Beijing car-body windows (deduplicated), using speed-normalised phone-compatible features. Applied to 20 m windows of our runs |
| Priority | `priority.py` | Gravity OD model from FY2025 station boardings gives riders crossing each spot. Consequence = riders, speed², ramp/aerial proximity |
| Validation | `inject.py`, `run_injection.py` | Planted car-body jolts (bounce + 8–13 Hz ring, both bogies) of known size |

## Key numbers from the 26 Sep 2026 survey

- 13 recordings, 4 phones, 6 trains (2 westbound, 4 eastbound). 2–13% of each recording removed as phone handling
- Agreement between recordings: same train 0.85, different trains on the same track 0.30, opposite track 0.20 (50 m scale; 0.30 vs 0.12 for the sharp-impact band)
- Confirmed zones: 300 m east of Expo/Crenshaw (4/4 eastbound trains, q = 0.049, on both tracks) and 365 m east of La Cienega/Jefferson (3/4 trains, line-wide p = 0.048, on both tracks, about 120 m from the foot of the aerial ramp)
- Wheel-locked vibration on the 09:58 eastbound (9×) and 10:30 westbound (17–22×) trains. Fitted wheel diameter 705–708 mm vs 711 mm new (P3010)
- Beijing held-out test: AUC 0.95 (any defect) and 0.98 (severe) with phone-compatible channels
- Detection with 4 trains: 75% for a 1.2 m/s² jolt, 0% for 0.6 m/s². Projected with a baseline: about 10 passes for 0.6 m/s², about 40 for 0.3 m/s²

## Limitations

One morning of data. Westbound has only 2 trains. No E Line ground truth yet, so zones are inspection candidates.
Phones sense the car body after two suspension stages: rough geometry and impacts, not hairline cracks.
Position is about 10 m from GPS, plus up to ±40 m for the unknown phone position within the train. Riders per segment are modeled.

## Data sources

- LA Metro rail GTFS: https://github.com/LACMTA/gtfs_rail
- Beijing Subway car-body vibration (CC-BY): https://github.com/Elscip/scidata_jrrt_1. Wang et al. 2022, Proc. IMechE Part F 236(9), and Wang et al. 2023, Applied Sciences 13(6):3457
- Station boardings (FY2025), line ridership, P3010 wheel diameter: Wikipedia station and vehicle articles
- Broken-rail cost figures: Schafer & Barkan 2008, AREMA (RailTEC, University of Illinois)
