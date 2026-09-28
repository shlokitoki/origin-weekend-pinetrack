# Origin Weekend: PineTrack

Primary research from Origin Weekend (26–27 September 2026).

## TrackScan

Four phones rode the LA Metro E Line between Expo Park/USC and Culver City and recorded vibration and GPS with phyphox. The analysis flags places on the corridor that are worth inspecting. It does **not** diagnose rail defects. See [`trackscan/AUDIT.md`](trackscan/AUDIT.md) for the method, corrections and limitations.

| Path | Contents |
|---|---|
| `*.xlsx` | 11 raw phyphox exports (Accelerometer, Location and Metadata sheets) from 26 Sep 2026 |
| `TrackScan Results/` | Original analysis: `code/` (Python + R pipeline, E Line GTFS geometry), charts, hotspot CSVs, `web_data/`. The audit supersedes its headline results. |
| `TrackScan Audit/` | 27 Sep re-analysis that separates westbound and eastbound evidence, with scripts and intermediate CSVs |
| `trackscan/` | Static map website (MapLibre) built from the audited data |

### View the site

```sh
cd trackscan
python3 -m http.server 8765
```

Then open http://localhost:8765.

### Re-run the audit

```sh
pip install pandas numpy scipy openpyxl matplotlib
python3 "TrackScan Audit/audit_recordings.py"
python3 "TrackScan Audit/reprocess_windows.py"
python3 "TrackScan Audit/build_directional_data.py"
python3 "TrackScan Audit/verify_directional_data.py"
```

The scripts read the `.xlsx` files from the repo root. The first run caches them in `TrackScan Audit/cache/`, which is not committed. `build_directional_data.py` rewrites `trackscan/data/`.

## Screwge pivot

- `Screwge Pivot The Project Memory Layer.docx`: pitch and evidence for the project memory layer
- `Screwge_Pivot_SuryaPass.pdf`: Screwge pivot report
