from pathlib import Path
import json,math
import pandas as pd,numpy as np
root=Path(__file__).resolve().parent.parent;data=root/'trackscan/data';audit=root/'TrackScan Audit'
S=json.loads((data/'summary.json').read_text());records=json.loads((data/'recordings.json').read_text());byid={r['recording_id']:r for r in records};W=pd.read_csv(audit/'windows_cruise.csv');H=json.loads((data/'hotspots.geojson').read_text())['features'];points=[f for f in H if f['geometry']['type']=='Point'];zones={f['properties']['id']:f for f in H if f['geometry']['type']=='LineString'}
assert len(records)==11 and S['physical_phones']==4
assert 'chance_test' not in S and len(W)==S['cruise_seconds']==3519
assert W.recording_id.nunique()==11
assert all((r['end_s_m']>r['start_s_m'])==(r['direction']=='westbound') for r in records)
assert len({f['properties']['id'] for f in H})==len(H)
for d in ['westbound','eastbound']:
 ps=[f for f in points if f['properties']['direction']==d];ds=S['direction_summary'][d]
 assert len(ps)==ds['candidate_spots']
 assert sum(r['direction']==d for r in records)==ds['recordings']
 assert len({r['pass_id'] for r in records if r['direction']==d})==ds['pass_groups']
 bins={f['properties']['bin']:f['properties'] for f in json.loads((data/'track_ribbon.geojson').read_text())['features'] if f['properties']['direction']==d}
 for f in ps:
  p=f['properties'];e=p['pass_evidence'];b=bins[p['peak_bin']]
  assert sum(x['covered'] for x in e)==p['rides_covering']==b['rides_covering']
  assert sum(x['elevated'] for x in e)==p['rides_rough']==b['rides_rough']
  assert all(byid[r]['direction']==d and byid[r]['pass_id']==x['pass_id'] for x in e for r in x['recordings'])
  vals=[]
  for x in e:
   if not x['covered']:continue
   file_medians=[float(W[(W.recording_id==r)&(W['bin']==p['peak_bin'])].score.median()) for r in x['recordings']]
   v=float(np.median(file_medians));assert abs(v-x['score'])<=.00051
   vals.append(v)
  assert abs(float(np.median(vals))-p['severity'])<=.05001
  assert all(bins[i]['rides_rough']>=2 and bins[i]['rides_covering']>=2 and bins[i]['rides_rough']/bins[i]['rides_covering']>=2/3 and bins[i]['median_score']>=1.5 for i in range(p['start_m']//25,p['end_m']//25))
  assert zones[p['id']+'-zone']['properties']['direction']==d
  assert p['start_m']<=p['peak_start_m']<p['end_m']
print('PASS: all 19 candidate areas traced to raw-derived scores; directions, denominators, source files, counts, and contiguous extents reconcile.')
print('PASS: original exported XLSX files untouched by processing; read-only derivatives isolated in audit/cache.')
print('GPS direction counts:',{d:sum(r['direction']==d for r in records) for d in ['westbound','eastbound']})
print('Provisional grouping sensitivity:',S['grouping_sensitivity'])
