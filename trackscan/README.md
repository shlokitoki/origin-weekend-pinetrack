# TrackScan: places worth inspecting

This is an inspection-screening map. It does not diagnose broken rails or confirm defects. Westbound and eastbound evidence is now analyzed separately.

## Run

```sh
python3 -m http.server 8765
```

Open http://localhost:8765. Upload the same contents to a static Replit project; no build or API keys are required. Internet is required for MapLibre, map tiles, and optional EXIF support.

## Data and corrections

- Four physical phones, confirmed by the user; eleven recording exports.
- Six westbound recordings (USC → Culver City) in two inferred pass groups.
- Five eastbound recordings (Culver City → USC) in three inferred pass groups.
- Pass groups come from metadata timestamps and GPS trajectories, not unique train identifiers. Arjan's 10:07 return recording is provisionally separate from the 09:58 return group. A clock offset or user confirmation could change that grouping.
- The current screen yields 7 westbound and 12 provisional eastbound candidate areas. Merging Arjan with the earlier return group would yield 7 eastbound areas. These are screening-rule outputs, not confirmed track defects.
- The old pooled H- hotspots, “rough on every ride” claims, and chance-test statistic are superseded. The website uses new WB-/EB- identifiers and recalculated directional scores.
- Sampled corridor span is 9.7 km rounded, calculated from retained moving GPS samples along the reference. Repeated rides are not added to this distance.

All original files remain in the source workspace's `TrackScan Results` folder. The files under this site's `data/` are corrected derived outputs. `AUDIT.md` describes the evidence, limitations, sources, and reproducible analysis in detail.

## Method

The supplied signal filtering, cruise-window selection, speed adjustment, and per-recording normalization were rerun from the original exports. Median scores are calculated within each recording/bin, across recordings within each pass/bin, and finally across covering passes of one direction. Thus simultaneous phones do not add independent repeat counts.

A pass/bin is elevated when it falls in the top decile of that pass's covered bin scores. Candidate bins need at least two covered passes, at least two elevated passes, elevated fraction >= 2/3, and directional median score >= 1.5. Only adjacent qualifying bins merge. The panel reports severity and repeatability for the selected peak slice. These are transparent screening thresholds, not a validated defect-detection model.

Both directions use the supplied GTFS corridor reference geometry. No fabricated parallel track offsets or rail-level accuracy are claimed. Directional filtering separates the evidence; it does not verify actual physical track assignment. Phone GPS accuracy and possible shared-track operation prevent that inference.

## Page controls

Travel direction changes the ribbon, candidate list, evidence, and tour direction together. Location and map cards select a candidate. The Evidence tab lists covering pass groups and source recordings. Checks are separate for each candidate and stored only in memory.

Orbit rotates/tilts, Move pans, Plan is north-up. The 45-second tour follows the selected direction and slows around its candidates. Pause, resume, and stop are supported. Changing direction stops playback.

## Photos and later charts

`data/photos.json` is an empty optional array. Put photo files in `photos/` beside `index.html`. Each entry accepts `file`, `caption`, optional `lat`/`lon`, and optional `hotspot_id` using the new WB-/EB- IDs. Missing coordinates are read from JPEG EXIF if possible. Photos associate by matching ID or proximity within 75 m, and open in a lightbox.

`#trace-slot` remains available for later vibration charts. `#analysis` now explains the corrected method and includes an expandable recording-to-direction audit.
