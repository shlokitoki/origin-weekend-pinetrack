# Pinetrack: places worth inspecting

This is an inspection-screening map. It does not diagnose broken rails or confirm defects. Westbound and eastbound evidence is now analyzed separately.

## Run locally

Static, with alerts on screen only (the same as the Vercel site):

```sh
python3 -m http.server 8765
```

Open http://localhost:8765. Internet is required for MapLibre and the map tiles.

With the email server (Node 20 or newer):

```sh
npm install
npm start
```

Open http://localhost:3000. Without SMTP settings the server runs with email off and prints which settings are missing. To email alerts, set these environment variables:

| Variable | Meaning |
|---|---|
| `SMTP_HOST` | SMTP server, for example `smtp.gmail.com` |
| `SMTP_PORT` | Optional, default `587`; use `465` for implicit TLS |
| `SMTP_USER`, `SMTP_PASS` | SMTP login; for Gmail, an app password |
| `SMTP_FROM` | Optional sender, for example `Pinetrack <you@example.com>` |
| `DEMO_ALERT_EMAIL` | The team inbox. You can instead edit the `DEMO_ALERT_EMAIL` constant at the top of `server.js` |

## Run on Replit

1. Create a Node.js Repl and upload this folder's contents: `index.html`, `alert-rules.js`, `server.js`, `package.json`, `package-lock.json`, `.replit` and `data/`. Leave out `node_modules`, `.vercel` and `.env.local`.
2. In Secrets, add `SMTP_HOST`, `SMTP_USER` and `SMTP_PASS`, plus `SMTP_PORT`, `SMTP_FROM` and `DEMO_ALERT_EMAIL` as needed. A `DEMO_ALERT_EMAIL` secret keeps the inbox address out of the code.
3. Press Run. `.replit` installs the dependencies and starts `server.js` on port 3000, published on port 80. The console says whether alert emails are on.

## Automatic alerts

During Ride the line, each spot the train reaches is checked against the rule in `alert-rules.js`, which reads its thresholds from `data/summary.json`. A spot at the Inspect level fires one alert per page load: a toast over the map, a row in the Alerts tab, and a pulse on step 6 of the How Pinetrack works strip. The recipient is always E Line Track Maintenance, configured by the agency; in the demo it is the team inbox.

With the email server, the page posts only the spot ID to `/api/alert`. The server rebuilds the alert from its own copy of the data files and emails `DEMO_ALERT_EMAIL`; the browser never chooses the recipient or the content. The server sends at most one email per spot every 30 seconds and 60 per hour (`ALERT_MAX_PER_HOUR`). When email is off or fails, the alert stays on screen and the viewer sees no error. The inspector buttons (issue found / nothing found) update the status on the page only.

Vercel serves this folder as a static site; `.vercelignore` leaves the server files out, so alerts there are on screen only.

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

Travel direction changes the ribbon, candidate list, evidence, and tour direction together. Location and map cards select a candidate. The Evidence tab lists covering pass groups and their source recordings; the phone recordings are the only evidence. The Alerts tab lists the alerts sent during this page load; a row opens the full alert with its location, evidence, suggested checks and inspector buttons.

Orbit rotates/tilts, Move pans, Plan is north-up. The 45-second tour follows the selected direction and slows around its candidates. Pause, resume, and stop are supported. Changing direction stops playback.

## Second analysis and vibration traces

Below How we measured it, the page shows a second, stricter analysis from `../Pinetrack Zone Analysis`: 13 recordings (the 11 above plus two from a 12:09 eastbound train), 6 trains and 20 m segments, with zones kept only where independent trains agree under a permutation test and a false-discovery-rate cut. It lists 7 zones, 3 confirmed and 4 probable, from `data/e_line_hotspot_zones.csv`, followed by three of its figures in `figures/`. A zone's "On our map" column lists the map's spots within 50 m of it. Selecting one opens that spot on the map.

Each spot's Evidence tab draws a vibration trace from `data/zone_analysis.json`. It shows every train in the spot's direction, and their average, ±700 m around the spot, as in the report's zone-trace figure. Rebuild that file with `python "../Pinetrack Zone Analysis/export_site_data.py"` after re-running the analysis.

`#analysis` explains the map's corrected method and includes an expandable recording-to-direction audit.

The site describes the Pinetrack sensor throughout. The demo recordings came from phones standing in for the sensor, and the note at the top of How we measured it is the one place that says so. The site's copies in `figures/` are therefore cropped: each figure's title and source line appear as page text, and "from phone tilt" reads "from tilt". The originals are unchanged in `../Pinetrack Zone Analysis/figures`.
