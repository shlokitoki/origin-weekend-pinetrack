from pathlib import Path
import importlib.util,json
import pandas as pd,numpy as np
ROOT=Path(__file__).resolve().parent.parent;OUT=ROOT/'TrackScan Audit'
spec=importlib.util.spec_from_file_location('trackscan_original',ROOT/'TrackScan Results/code/trackscan.py');mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
mod.read_tables=lambda path:pd.read_pickle(OUT/'cache'/(Path(path).stem+'.pkl'))
line=mod.Line(json.loads((ROOT/'TrackScan Results/code/eline.json').read_text())['shape'])
infos=[];wins=[]
for i,p in enumerate(sorted(ROOT.glob('*.xlsx'))):
 info,w=mod.process_run(str(p),line);info['recording_id']=f'R{i+1:02d}';assert w is not None,info
 w['recording_id']=info['recording_id'];w['direction']=info['direction'];infos.append(info);wins.append(w);print(info['recording_id'],info['direction'],len(w),flush=True)
S=pd.DataFrame(infos);S.to_csv(OUT/'recordings_reprocessed.csv',index=False)
W=pd.concat(wins,ignore_index=True);W.to_csv(OUT/'windows_all_phases.csv',index=False);W=W[W.phase=='cruise'].copy()
b,a=np.polyfit(np.log(W.rms),np.log(W.speed),1) if False else np.polyfit(np.log(W.speed),np.log(W.rms),1)
b=float(np.clip(b,0,2));W['adj']=W.rms/np.power(W.speed,b);W['score']=W.adj/W.groupby('recording_id').adj.transform('median');W['bin']=(W.s//25).astype(int);W.to_csv(OUT/'windows_cruise.csv',index=False)
(OUT/'processing_summary.json').write_text(json.dumps({'moving_seconds':sum(x['moving_windows'] for x in infos),'cruise_seconds':len(W),'speed_exponent':b},indent=2));print('DONE',len(W),'cruise seconds; exponent',b,flush=True)
# Compare synchronized GPS traces to distinguish simultaneous phones from repeat passes.
gps=pd.read_csv(OUT/'gps_audit.csv');pairs=[]
for i,x in enumerate(infos):
 for y in infos[i+1:]:
  if x['direction']!=y['direction']:continue
  A=gps[(gps.recording_id==x['recording_id'])&(gps.hacc<=40)&(gps.offset<=60)].sort_values('epoch');B=gps[(gps.recording_id==y['recording_id'])&(gps.hacc<=40)&(gps.offset<=60)].sort_values('epoch')
  lo=max(A.epoch.min(),B.epoch.min());hi=min(A.epoch.max(),B.epoch.max())
  if hi-lo<60:continue
  times=np.arange(lo,hi,5);ds=np.abs(np.interp(times,A.epoch,A.s)-np.interp(times,B.epoch,B.s));pairs.append({'a':x['recording_id'],'b':y['recording_id'],'overlap_seconds':hi-lo,'median_separation_m':float(np.median(ds)),'p90_separation_m':float(np.quantile(ds,.9))})
(OUT/'gps_pair_comparisons.json').write_text(json.dumps(pairs,indent=2));print(json.dumps(pairs,indent=2))
