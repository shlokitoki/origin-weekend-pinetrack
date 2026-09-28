"""Rebuild the website from raw-export windows, preserving the supplied originals.
Run audit_recordings.py and reprocess_windows.py first. No opposite-direction pooling.
"""
from pathlib import Path
import json,math,importlib.util,copy
import numpy as np,pandas as pd
ROOT=Path(__file__).resolve().parent.parent;OUT=ROOT/'TrackScan Audit';DATA=ROOT/'trackscan/data'
spec=importlib.util.spec_from_file_location('original',ROOT/'TrackScan Results/code/trackscan.py');mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
geo=json.loads((ROOT/'TrackScan Results/code/eline.json').read_text());line=mod.Line(geo['shape'])
records=json.loads((OUT/'recording_audit.json').read_text())
group_map={'R02':'WB-1','R06':'WB-1','R09':'WB-1','R03':'WB-2','R08':'WB-2','R10':'WB-2','R05':'EB-1','R07':'EB-1','R04':'EB-2','R01':'EB-3','R11':'EB-3'}
W=pd.read_csv(OUT/'windows_cruise.csv');W['pass_id']=W.recording_id.map(group_map)
# Median within recording/bin; median across simultaneous phones; equal pass weighting.
R=W.groupby(['direction','bin','pass_id','recording_id']).score.median()
P=R.groupby(['direction','bin','pass_id']).median()
thresholds=P.groupby(['direction','pass_id']).quantile(.9)
original=ROOT/'TrackScan Results/web_data'
ribbon_by_bin={f['properties']['bin']:f for f in json.loads((original/'track_ribbon.geojson').read_text())['features']}
rough_by_bin={f['properties']['bin']:f for f in json.loads((original/'track_roughness.geojson').read_text())['features']}
stations=json.loads((original/'stations.geojson').read_text())['features'];st=sorted([f['properties'] for f in stations],key=lambda x:x['chainage_m']);bus=pd.read_csv(ROOT/'TrackScan Results/code/stops_corridor.csv')
def coord(s):
 lat,lon=line.point_at(s);return [float(lon),float(lat)]
def clip(a,b):
 out=[coord(a)];out.extend([[float(lon),float(lat)] for s,lat,lon in zip(line.cum,line.lat,line.lon) if a<s<b]);out.append(coord(b));return out
def cross(c):
 d=np.hypot((bus.stop_lat-c[1])*110950,(bus.stop_lon-c[0])*mod.M_LON);i=d.idxmin();return str(bus.loc[i,'stop_name']) if d[i]<150 else None
ribbons=[];rough=[];hotspots=[];dsummary={};bin_tables=[]
for direction,prefix in [('westbound','WB'),('eastbound','EB')]:
 per=P.loc[direction].unstack('pass_id');per=per.reindex(columns=sorted(per.columns));hot=per.ge(thresholds.loc[direction],axis=1)&per.notna();cov=per.notna().sum(axis=1);hc=hot.sum(axis=1);med=per.median(axis=1)
 counts=W[W.direction==direction].groupby('bin').recording_id.nunique()
 B=pd.DataFrame({'median_score':med,'rides_rough':hc,'rides_covering':cov,'recordings':counts}).reset_index();B['direction']=direction;bin_tables.append(B)
 for _,row in B.iterrows():
  b=int(row['bin']);props={'bin':b,'direction':direction,'start_m':b*25,'end_m':(b+1)*25,'median_score':round(float(row.median_score),3),'hot_fraction':float(row.rides_rough/row.rides_covering),'recordings':int(row.recordings),'rides_rough':int(row.rides_rough),'rides_covering':int(row.rides_covering),'location_precision':'approximate corridor location; physical track not resolved'}
  for lookup,target in [(ribbon_by_bin,ribbons),(rough_by_bin,rough)]:
   feature=copy.deepcopy(lookup[b]);feature['id']=f'{prefix}-{b}';feature['properties']=props.copy();target.append(feature)
 candidate=B[(B.rides_covering>=2)&(B.rides_rough>=2)&(B.rides_rough/B.rides_covering>=2/3)&(B.median_score>=1.5)].copy().sort_values('bin')
 zones=[]
 for _,z in candidate.groupby((candidate.bin.diff()!=1).cumsum()):
  peak=z.loc[z.median_score.idxmax()];b=int(peak['bin']);a=int(z.bin.min()*25);end=int((z.bin.max()+1)*25);c=coord(b*25+12.5);s=b*25+12.5;nearest=min(st,key=lambda x:abs(x['chainage_m']-s));before=[x for x in st if x['chainage_m']<=s];after=[x for x in st if x['chainage_m']>s];evidence=[]
  for pass_id in per.columns:
   val=per.loc[b,pass_id];evidence.append({'pass_id':pass_id,'covered':bool(pd.notna(val)),'score':round(float(val),3) if pd.notna(val) else None,'elevated':bool(hot.loc[b,pass_id]),'threshold':round(float(thresholds.loc[direction,pass_id]),3),'recordings':sorted(W[(W['bin']==b)&(W.pass_id==pass_id)].recording_id.unique().tolist())})
  props={'direction':direction,'between':before[-1]['name']+' → '+after[0]['name'],'cross_street':cross(c),'nearest_station':nearest['name'],'dist_to_station_m':int(round(abs(nearest['chainage_m']-s))),'length_m':end-a,'rides_rough':int(peak.rides_rough),'rides_covering':int(peak.rides_covering),'severity':round(float(peak.median_score),1),'start_m':a,'end_m':end,'peak_bin':b,'peak_start_m':b*25,'peak_end_m':b*25+25,'google_maps':f'https://www.google.com/maps?q={c[1]:.6f},{c[0]:.6f}','status':'Worth inspecting','location_precision':'Approximate corridor location; physical track unverified','pass_evidence':evidence,'evidence_scope':'Counts and severity refer to the selected peak 25 m slice; each adjacent included slice independently meets the candidate rule.'}
  zones.append((props,c))
 zones.sort(key=lambda x:(-x[0]['severity'],-x[0]['rides_rough'],x[0]['start_m']))
 for rank,(props,c) in enumerate(zones,1):
  props.update(id=f'{prefix}-{rank:02d}',rank=rank,label=f'{prefix}-{rank:02d} · {props["severity"]:.1f}×')
  hotspots.append({'type':'Feature','properties':props,'geometry':{'type':'Point','coordinates':c}})
  hotspots.append({'type':'Feature','properties':{'id':props['id']+'-zone','direction':direction,'rank':rank},'geometry':{'type':'LineString','coordinates':clip(props['start_m'],props['end_m'])}})
 dsummary[direction]={'pass_groups':len(per.columns),'recordings':int(W[W.direction==direction].recording_id.nunique()),'candidate_spots':len(zones),'candidate_slices':len(candidate),'covered_slices':len(per),'all_covered_passes_spots':sum(p['rides_rough']==p['rides_covering'] for p,c in zones),'from':'Expo Park/USC' if direction=='westbound' else 'Culver City','to':'Culver City' if direction=='westbound' else 'Expo Park/USC'}
for name,features in [('track_ribbon.geojson',ribbons),('track_roughness.geojson',rough),('hotspots.geojson',hotspots)]:
 (DATA/name).write_text(json.dumps({'type':'FeatureCollection','features':features},separators=(',',':'),allow_nan=False))
for r in records:
 r['pass_id']=group_map[r['recording_id']];r['grouping_status']='inferred from timestamps and GPS; independent train identity not verified';r['physical_phone_id']=None
public_records=[{k:v for k,v in r.items() if k not in ['events','start_epoch','end_epoch']} for r in records]
(DATA/'recordings.json').write_text(json.dumps(public_records,indent=2,allow_nan=False))
summary=json.loads((original/'summary.json').read_text());processing=json.loads((OUT/'processing_summary.json').read_text());summary.update(processing);summary['physical_phones']=4;summary['physical_phones_source']='User clarification on 2026-09-27';summary['recordings']=len(records);summary['direction_summary']=dsummary
summary['rides']=[]
for pass_id in sorted(set(group_map.values()),key=lambda g:min(r['start_epoch'] for r in records if r['pass_id']==g)):
 rows=[r for r in records if r['pass_id']==pass_id];summary['rides'].append({'pass_id':pass_id,'start_local':min(r['start_local'] for r in rows)[11:16],'direction':rows[0]['direction'],'recordings':len(rows),'grouping':'inferred'})
moving=pd.read_csv(OUT/'windows_all_phases.csv');summary['km_scanned']=round(float((moving.s.max()-moving.s.min())/1000),1);summary['corridor_extent_m']={'start':float(moving.s.min()),'end':float(moving.s.max())};summary['corridor_extent_definition']='Along-reference span between minimum and maximum retained moving samples; not a sum of repeat travel distances.'
def sensitivity(mode):
 v=W[W.direction=='eastbound'].copy()
 if mode=='merge':v.loc[v.recording_id=='R04','pass_id']='EB-1'
 if mode=='exclude':v=v[v.recording_id!='R04']
 rp=v.groupby(['bin','pass_id','recording_id']).score.median().groupby(['bin','pass_id']).median();pv=rp.unstack('pass_id');q=rp.groupby('pass_id').quantile(.9);hv=pv.ge(q,axis=1)&pv.notna();cv=pv.notna().sum(axis=1);n=hv.sum(axis=1);m=pv.median(axis=1);c=m[(cv>=2)&(n>=2)&(n/cv>=2/3)&(m>=1.5)]
 return int((c.index.to_series().diff()!=1).sum())
summary['grouping_sensitivity']={'eastbound_separate_arjan_candidate_areas':sensitivity('separate'),'eastbound_merge_arjan_with_earlier_candidate_areas':sensitivity('merge'),'eastbound_exclude_arjan_candidate_areas':sensitivity('exclude'),'status':'Sensitivity scenarios, not alternative observed truth. Normalized window scores retained; grouping and downstream thresholds recomputed.'}
summary['hotspots_listed']=sum(d['candidate_spots'] for d in dsummary.values());summary['audit_status']='Recomputed by travel direction; pass identities inferred, physical tracks unverified';summary['pending_confirmation']='Whether Arjan\u2019s 10:07 eastbound export was a separate train pass or has a clock offset; currently treated as a separate timestamp/GPS group.'
for k in ['chance_test','top3_all_rides','braking_median_decel_mps2'] : summary.pop(k,None)
summary['method']={'bin_m':25,'within_recording_bin':'median cruise-window score','within_pass_bin':'median across covering recordings','across_pass_bin':'median across covering passes of one direction','elevated_threshold':'top decile of each pass\u2019s covered bin scores','candidate_rule':'At least 2 covered passes, at least 2 elevated passes, elevated fraction >= 2/3, directional median score >= 1.5. Adjacent qualifying bins merge; counts refer to peak slice.','claim':'Places worth inspecting; not diagnoses of broken rails.','geometry':'Both directional views use the supplied GTFS corridor reference. No surveyed rail or track assignment is inferred.'}
(DATA/'summary.json').write_text(json.dumps(summary,indent=2,allow_nan=False));pd.concat(bin_tables).to_csv(OUT/'directional_bins.csv',index=False)
print(json.dumps(dsummary,indent=2));print('Wrote',len(hotspots)//2,'direction-specific inspection leads')
