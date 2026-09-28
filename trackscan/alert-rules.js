/* Pinetrack alert rules. Loaded by index.html in the browser and by server.js in Node, so the
   on-screen alerts and the emails apply the same rule to the same data and use the same wording. */
(function (root, factory) {
  if (typeof module === 'object' && module.exports) module.exports = factory();
  else root.PinetrackAlerts = factory();
})(typeof self !== 'undefined' ? self : this, function () {
  'use strict';

  // Stands in for the agency's track maintenance team; the agency configures the real recipient.
  const RECIPIENT = 'E Line Track Maintenance';
  const SUGGESTED_CHECKS = ['Street crossing at this spot', 'Switch or crossover', 'Rail joint condition', 'Visible rail or fastener defects', 'Track geometry (geometry car run)'];
  const times = n => Number(n).toFixed(1) + '×';
  const surveyDate = summary => new Intl.DateTimeFormat('en-US', { month: 'short', day: 'numeric', year: 'numeric', timeZone: 'UTC' }).format(new Date(summary.date + 'T12:00:00Z'));

  // summary.json states the candidate rule in words. Read its thresholds from there; the fallbacks are
  // the values "TrackScan Audit/build_directional_data.py" applied when it selected the map's spots.
  function rule(summary) {
    const text = (summary.method && summary.method.candidate_rule) || '';
    const number = (pattern, fallback) => { const m = text.match(pattern), n = m ? Number(m[1]) : NaN; return Number.isFinite(n) ? n : fallback; };
    const fraction = text.match(/fraction\s*>=\s*(\d+)\s*\/\s*(\d+)/i);
    return {
      binM: Number(summary.method && summary.method.bin_m) || 25,
      minCovering: number(/at least (\d+) covered passes/i, 2),
      minElevated: number(/at least (\d+) elevated passes/i, 2),
      fraction: fraction ? [Number(fraction[1]), Number(fraction[2])] : [2, 3],
      minScore: number(/median score\s*>=\s*(\d+(?:\.\d+)?)/i, 1.5)
    };
  }

  // Inspect meets the rule, so an alert is sent. Watch is elevated on a single pass: logged, no alert.
  // Urgent needs week-over-week trend history, which one day of recordings cannot provide.
  function level(p, r) {
    const [num, den] = r.fraction;
    if (p.rides_covering >= r.minCovering && p.rides_rough >= r.minElevated && p.rides_rough * den >= num * p.rides_covering && p.severity >= r.minScore) return 'inspect';
    return p.rides_rough === 1 ? 'watch' : null;
  }

  // Everything an alert says, taken from hotspots.geojson, summary.json and recordings.json.
  function describe(feature, summary, recordings) {
    const p = feature.properties, [lon, lat] = feature.geometry.coordinates, place = p.cross_street || p.nearest_station;
    const files = new Map(recordings.map(r => [r.recording_id, r.file]));
    const starts = new Map(summary.rides.map(r => [r.pass_id, r.start_local]));
    const route = summary.direction_summary[p.direction];
    const passes = p.pass_evidence.map(e => ({
      id: e.pass_id,
      start: starts.get(e.pass_id) || '',
      result: e.covered ? (e.elevated ? 'elevated' : 'below threshold') + ' · ' + times(e.score) : 'no usable samples at this slice',
      files: e.recordings.map(id => files.get(id) || id)
    }));
    return {
      id: p.id,
      direction: p.direction,
      severity: times(p.severity),
      place,
      title: 'Near ' + place,
      subject: `Pinetrack alert · ${p.id} · ${times(p.severity)} · Near ${place}`,
      what: `Vibration ${times(p.severity)} typical at a ${p.peak_end_m - p.peak_start_m} m slice, elevated on ${p.rides_rough} of ${p.rides_covering} ${p.direction} passes.`,
      where: `Near ${place}, ${p.dist_to_station_m} m from ${p.nearest_station} station`,
      route: `${p.direction === 'westbound' ? 'Westbound' : 'Eastbound'} (${route.from} → ${route.to})`,
      latlon: `${lat.toFixed(5)}, ${lon.toFixed(5)}`,
      mapUrl: p.google_maps,
      recorded: `${surveyDate(summary)} · ${p.pass_evidence.filter(e => e.covered).reduce((n, e) => n + e.recordings.length, 0)} sensor recordings`,
      passes,
      // Eastbound pass grouping depends on an unconfirmed recording (summary.pending_confirmation).
      provisional: p.direction === 'eastbound',
      checks: SUGGESTED_CHECKS
    };
  }

  return { RECIPIENT, SUGGESTED_CHECKS, times, surveyDate, rule, level, describe };
});
