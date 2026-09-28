from pathlib import Path
import json,sys,importlib.util
import pandas as pd,numpy as np
ROOT=Path(__file__).resolve().parent.parent
OUT=ROOT/'TrackScan Audit';(OUT/'cache').mkdir(exist_ok=True)
spec=importlib.util.spec_from_file_location('original_trackscan',ROOT/'TrackScan Results/code/trackscan.py');mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
line=mod.Line(json.loads((ROOT/'TrackScan Results/code/eline.json').read_text())['shape'])
allgps=[];records=[]
for i,p in enumerate(sorted(ROOT.glob('*.xlsx'))):
 c=OUT/'cache'/(p.stem+'.pkl')
 if c.exists():tables=pd.read_pickle(c)
 else:
  tables=pd.read_excel(p,sheet_name=['Accelerometer','Location','Metadata Time','Metadata Device']);pd.to_pickle(tables,c)
 gps=mod.find_gps(tables);s,off=line.project(gps.lat,gps.lon);gps['s']=s;gps['offset']=off
 meta=tables['Metadata Time'];starts=meta[meta.event=='START'];mt=starts['experiment time'].to_numpy(float);me=starts['system time'].to_numpy(float);idx=np.maximum(0,np.searchsorted(mt,gps.t,side='right')-1);gps['epoch']=me[idx]+gps.t.to_numpy()-mt[idx]
 device=dict(tables['Metadata Device'].iloc[:,:2].values)
 row={'file':p.name,'recording_id':f'R{i+1:02d}','model':device.get('deviceModel'),'version':device.get('deviceRelease'),'start_local':pd.to_datetime(me[0],unit='s',utc=True).tz_convert('America/Los_Angeles').isoformat(),'start_epoch':me[0],'end_epoch':float(gps.epoch.max()),'end_local':pd.to_datetime(gps.epoch.max(),unit='s',utc=True).tz_convert('America/Los_Angeles').isoformat(),'start_s_m':float(np.median(s[:10])),'end_s_m':float(np.median(s[-10:])),'direction':'westbound' if np.median(s[-10:])>np.median(s[:10]) else 'eastbound','hacc_median':float(gps.hacc.median()),'hacc_p90':float(gps.hacc.quantile(.9)),'events':meta.to_dict('records')}
 records.append(row);gps['file']=p.name;gps['recording_id']=row['recording_id'];allgps.append(gps);print(json.dumps({k:v for k,v in row.items() if k!='events'}),flush=True)
pd.concat(allgps).to_csv(OUT/'gps_audit.csv',index=False);(OUT/'recording_audit.json').write_text(json.dumps(records,indent=2,default=str))
