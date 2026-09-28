# Pinetrack direction and recording audit

Audit date: 27 September 2026. Original workbook exports and the original `TrackScan Results` folder remain unchanged. The website's derived data has been replaced; the original headline counts and rankings are superseded.

## What the results mean

**Pinetrack finds places worth inspecting. It does not diagnose broken rails.** Phone vibration can reflect vehicles, suspension, speed, crossings, track geometry, positioning error, or other causes. These are screening leads, not confirmed defects or rail-level locations.

## Confirmed corrections

1. **Four physical phones, eleven recording exports.** The physical phone count comes from the user's clarification. A recording is not a separate phone, and simultaneous phone recordings are not independent train passes. Device model strings do not uniquely identify a handset.
2. **Opposite directions must not be pooled as repeat evidence on one track.** The original processing assigned each recording a direction correctly, but `finalize.py` combined both directions for hotspot repeatability and applied a priority bonus for “both directions.” All displayed route geometry also used one GTFS shape. That supports a common corridor location, not proof that the same physical track was affected.
3. **The old ride-level event was an OR across phones and across merged zone bins.** One phone or a different slice elsewhere in a merged area could qualify a whole ride. The updated aggregation combines simultaneous recordings before counting pass-level evidence; the displayed count refers to one specified peak slice.
4. **Do not reuse the old chance test.** It was based on the former aggregation and is removed from the revised website summary. No new statistical significance claim is made.

## Direction and pass grouping from the raw exports

Direction was rechecked from GPS progression projected onto the supplied corridor geometry. All 11 assignments agree with the original recording direction column. Westbound means Expo Park/USC toward Culver City; eastbound means Culver City toward Expo Park/USC.

| Inferred pass group | Recorded start | Direction | Files |
|---|---|---|---|
| WB-1 | 09:34 | USC → Culver City | Track Scan 09-51-58; track_brooke_1; track_suhela_1 |
| EB-1 | 09:58 | Culver City → USC | track2 10-14-40; track_brooke_2 |
| EB-2 | 10:07 | Culver City → USC | Track record arjan 10-23-58 |
| WB-2 | 10:30 | USC → Culver City | Track Scan 10-49-47; track_brooke_3; track_suhela_3 |
| EB-3 | 11:25 | Culver City → USC | 3 11-43-20; track_suhela_4 |

These are five **inferred recording/pass groups**, not five verified train identities. They represent two westbound groups (six files) and three eastbound groups (five files). Metadata and overlapping GPS traces were used; filenames' export times were not treated as ride start times. Pause/resume metadata was accounted for when comparing wall-clock GPS trajectories.

Arjan's 10:07 eastbound file overlaps the 09:58 group in wall-clock time, but their median along-corridor separation during that overlap is approximately 5.98 km. This supports a separate pass if device clocks are synchronized. A user confirmation of whether it was a different train or an offset clock remains pending. It has not silently been merged into the earlier group. No unique train identifier is present in the exports.

## Recalculation

Signal processing was rerun from all eleven XLSX exports with the supplied processor: gravity-projected vertical acceleration, 1–30 Hz bandpass, approximately one-second RMS windows, accepted GPS, minimum moving speed, and estimated braking/accelerating/station-buffer exclusion. This reproduced 7,174 retained moving phone-windows and 3,519 cruise phone-windows. These are sums across recordings, not independent train-seconds. The fitted speed exponent was 1.0172022529, followed by per-recording median normalization. The speed correction is an estimate; it does not eliminate all vehicle or operating-condition effects.

Revised aggregation, explicitly different from the supplied maximum/OR method:

1. Median of cruise-window scores within each recording and 25 m bin.
2. Median across recordings in each inferred pass and bin; phones in one pass do not add independent repeats.
3. Median across covering pass groups, separately for each direction.
4. A pass/bin is elevated when its score is at or above the 90th percentile of that pass's covered-bin scores.
5. A candidate bin must have at least two covering pass groups, at least two elevated groups, elevated fraction at least 2/3, and directional median score at least 1.5.
6. Merge only immediately adjacent qualifying bins. No 75 m gaps are bridged. Displayed severity and repeatability refer to the candidate area's peak slice; every included slice independently meets the candidate rule.

These thresholds are a transparent screening choice, not a validated rail-defect classifier. The small number of inferred passes is not enough for a strong general repeatability or safety claim. No statistical significance is claimed.

The revised screen yields **7 westbound candidate areas (8 bins)** and **12 eastbound candidate areas (17 bins)**. They are direction-specific leads; do not add them and call the result distinct physical defects. New WB-/EB- identifiers distinguish them from the superseded pooled H- rankings.

The Arjan grouping materially changes the return-direction result: treating it as part of the earlier return pass yields 7 eastbound candidate areas, versus 12 when separate. Excluding it also yields 7. These are sensitivity scenarios, not evidence that one grouping is correct; the website labels the eastbound result provisional.

The revised sampled corridor extent is 9.7 km when rounded to one decimal, calculated from the minimum and maximum retained moving-sample chainages (15,253.71 to 24,922.97 m). This replaces the supplied 9.6 km headline estimate; it is a corridor span, not the sum of travel on repeat passes.

## Geometry and uncertainty

The engineering record describes the Expo corridor as double-track. Metro also documents exceptional shared-track operation during works; direction is therefore not a guaranteed physical track identifier. Phone GPS and the supplied route shape cannot establish which particular track/rail a train used on the recording date.

The exports' median reported horizontal accuracy ranges from approximately 5.37 m to 15.21 m; some 90th percentiles exceed 40 m. These reported accuracy values are not guaranteed error bounds. GTFS geometry is intended to represent transit travel paths and can stay within a group of tracks when individual track use varies. We therefore retain the supplied corridor geometry as a clearly labelled approximate reference in each direction view, and do not invent lateral offsets to draw fabricated separate tracks. Actual track assignment needs operator track/dispatch records or surveyed direction-specific geometry plus sufficiently precise positioning.

## Research sources

- CPUC Decision 09-09-019, lines 17–23: double-track Expo corridor and Culver City crossing structure. https://docs.cpuc.ca.gov/PUBLISHED/FINAL_DECISION/106853.htm
- Metro, 28 October 2015: temporary sharing of the Culver City-bound track at Expo/Crenshaw and Farmdale. This demonstrates an operational exception, not conditions on the recording date. https://thesourcearchives.metro.net/2015/10/28/late-night-saturday-through-sunday-bus-shuttles-replace-expo-line-btwn-expola-brea-and-culver-city-station/
- GTFS shape guidance: track-following travel paths, with geometry allowed within the range of possible tracks when track usage varies. https://gtfs.org/resources/gtfs-schedule-feature-guides/shapes/
- GPS.gov: smartphone accuracy and degradation around buildings, bridges and trees. https://www.gps.gov/gps-accuracy-0

## Reproducibility and retained evidence

`recording_audit.json` contains workbook metadata and directional endpoints. `gps_audit.csv` and `gps_pair_comparisons.json` support the timestamp/trajectory comparisons. `windows_all_phases.csv` and `windows_cruise.csv` retain reprocessed measurement windows. `directional_bins.csv` contains the revised per-direction scores and counts. The three Python scripts rerun extraction, window processing and the website data generation; cached tables are read-only derivatives of the original workbooks. The website includes an expandable recording-to-direction table and pass evidence for each candidate's peak slice.
