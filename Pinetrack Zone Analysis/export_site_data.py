"""Export this analysis for the website: writes trackscan/data/zone_analysis.json.

Reads out/dashboard_data.json (per-train roughness per 20 m, track line, stations, zones) and the
presentation zone table trackscan/data/e_line_hotspot_zones.csv (status, repair order, Street View links).
Run from anywhere: python "Pinetrack Zone Analysis/export_site_data.py"
"""
import csv, json, os

HERE = os.path.dirname(os.path.abspath(__file__))
SITE_DATA = os.path.join(HERE, '..', 'trackscan', 'data')

D = json.load(open(os.path.join(HERE, 'out', 'dashboard_data.json')))
rows = list(csv.DictReader(open(os.path.join(SITE_DATA, 'e_line_hotspot_zones.csv'), encoding='utf-8')))
r2 = lambda v: None if v is None else round(v, 2)

seg_s = [sg['s'] for sg in D['segs']['EB']]
assert seg_s == [sg['s'] for sg in D['segs']['WB']]
trains = []
for k in sorted(D['prof'], key=int):
    p = D['prof'][k]
    assert len(p['vals']) == len(seg_s)
    trains.append({'dir': p['dir'], 'start': p['start'], 'phones': p['phones'], 'vals': [r2(v) for v in p['vals']]})

zones = []
for z, row in zip(D['zones'], rows):
    assert z['where'] == row['where'] and float(row['chainage_from_m']) == z['s_from'] and float(row['chainage_to_m']) == z['s_to'], (z['where'], row['where'])
    zones.append({'zone': int(row['zone']), 'status': 'Confirmed' if row['status'].startswith('Confirmed') else 'Probable',
                  'where': row['where'], 'dirs': row['dirs'], 'both_tracks': row['both_tracks'] == 'True',
                  's_from': z['s_from'], 's_to': z['s_to'], 's_peak': z['s_peak'],
                  'trains_agree': int(row['trains_agree']), 'n_trains': int(row['n_trains']), 'fdr_q': float(row['fdr_q']),
                  'defect_model_prob': float(row['defect_model_prob']), 'speed_mph': float(row['speed_mph']),
                  'near_ramp': row['near_ramp'] == 'True', 'repair_order': int(row['repair_order']),
                  'lat': float(row['lat']), 'lon': float(row['lon']), 'street_view': row['street_view']})

out = {'source': '13 phyphox recordings (4 phones, 6 trains) on LA Metro E Line, 26 Sep 2026; LA Metro GTFS track geometry',
       'measure': 'Roughness vs. normal track at the same speed (sigma) per 20 m of track; each train is the median of the phones aboard',
       'seg_s': [round(s) if float(s).is_integer() else s for s in seg_s],
       'trains': trains,
       'line': [[round(a, 6), round(o, 6)] for a, o in D['line']], 'line_s': [round(s, 1) for s in D['sline']],
       'stations': [{'name': st['name'], 's': st['s']} for st in D['stations']],
       'zones': zones}
json.dump(out, open(os.path.join(SITE_DATA, 'zone_analysis.json'), 'w'), separators=(',', ':'), ensure_ascii=False)
print(f"Wrote {len(trains)} trains, {len(zones)} zones, {len(seg_s)} segments to trackscan/data/zone_analysis.json")
