import pandas as pd, numpy as np, json, math, os, matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
BIN=25
OUT=os.environ.get('OUT','out')
W=pd.read_csv(f'{OUT}/windows.csv'); S=pd.read_csv(f'{OUT}/runs_summary.csv').sort_values('start_epoch')
ride=[];r=0;last=None
for e in S['start_epoch']:
    if last is None or e-last>180: r+=1
    ride.append(r); last=e
S['ride']=ride
W=W.merge(S[['run','ride','direction']],on='run'); W['bin']=(W['s']//BIN).astype(int)
per=W.groupby(['bin','run'])['score'].max().unstack('run')
p90=W.groupby('run')['score'].quantile(0.9)
hot=per.ge(p90,axis=1)&per.notna()
run2ride=dict(zip(S.run,S.ride))
ride_hot=hot.T.groupby(run2ride).any().T; ride_cov=per.notna().T.groupby(run2ride).any().T
ride_dir={rd:S[S.ride==rd].direction.iloc[0] for rd in S.ride.unique()}
ride_time={rd:S[S.ride==rd].start_local.iloc[0][:5] for rd in S.ride.unique()}
med=per.median(axis=1)
H=pd.read_csv(f'{OUT}/hotspots.csv').sort_values('start_m')
geo=json.load(open('eline.json'))
bs=pd.read_csv('stops_corridor.csv'); M_LAT=110950; M_LON=111320*math.cos(math.radians(34.03))
def cross(lat,lon):
    d=np.hypot((bs.stop_lat-lat)*M_LAT,(bs.stop_lon-lon)*M_LON); i=d.idxmin()
    n=bs.loc[i,'stop_name']; return (n if d[i]<150 else None)
# merge hotspots within 75 m into zones
zones=[];cur=None
for _,h in H.iterrows():
    if cur is not None and h.start_m-cur['end_m']<=75:
        cur['end_m']=max(cur['end_m'],h.end_m); cur['members'].append(h)
    else:
        if cur: zones.append(cur)
        cur=dict(start_m=h.start_m,end_m=h.end_m,members=[h])
zones.append(cur)
rows=[]
for z in zones:
    b0,b1=int(z['start_m']//BIN),int((z['end_m']-1)//BIN); bins=[b for b in range(b0,b1+1) if b in ride_hot.index]
    rh=ride_hot.loc[bins].any(); rc=ride_cov.loc[bins].any()
    hr=[rd for rd in rh.index if rh[rd]]
    dirs=sorted({ride_dir[rd] for rd in hr})
    top=max(z['members'],key=lambda m:m.median_score*m.repeat_rate)
    mid=(z['start_m']+z['end_m'])/2
    sub=med.loc[[b for b in range(b0,b1+1) if b in med.index]]
    pk=int(sub.idxmax()); pk_s=pk*BIN+BIN/2
    la=float(np.interp(pk_s, *[np.array(x) for x in zip(*[(0,0)])])) if False else None
    rows.append(dict(start_m=z['start_m'],end_m=z['end_m'],peak_bin=pk,lat=top.lat,lon=top.lon,
        between=top['between'],nearest_station=top.nearest_station,dist_to_station_m=int(top.dist_to_station_m),
        cross_street=cross(top.lat,top.lon),rides_rough=len(hr),rides_covering=int(rc.sum()),
        both_directions=len(dirs)==2,severity=round(float(sub.max()),1),
        repeat=round(len(hr)/max(1,int(rc.sum())),2)))
Z=pd.DataFrame(rows)
Z['priority']=Z['severity']*Z['repeat']*(1+0.25*Z['both_directions'])
Z=Z[(Z.rides_rough>=3)].sort_values('priority',ascending=False).reset_index(drop=True)
Z.insert(0,'rank',range(1,len(Z)+1))
Z['length_m']=(Z.end_m-Z.start_m).astype(int)
Z['google_maps']=[f"https://www.google.com/maps?q={a},{b}" for a,b in zip(Z.lat,Z.lon)]
out=Z[['rank','between','cross_street','nearest_station','dist_to_station_m','length_m','rides_rough','rides_covering','both_directions','severity','lat','lon','google_maps','start_m','end_m']]
out.to_csv(f'{OUT}/TrackScan_hotspots.csv',index=False)
print(out.drop(columns=['google_maps']).to_string(index=False))

# ---------------- chart
SURF='#fcfcfb'; INK='#0b0b0b'; INK2='#52514e'; MUTED='#898781'; GRID='#e1e0d9'; AXIS='#c3c2b7'
BLUE='#2a78d6'; CRIT='#d03b3b'
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'text.color':INK,'axes.labelcolor':INK2,'xtick.color':MUTED,'ytick.color':MUTED})
x=(per.index*BIN+BIN/2)/1000
lo,hi=x.min(),x.max()
fig=plt.figure(figsize=(13,7.2),facecolor=SURF)
gs=fig.add_gridspec(2,1,height_ratios=[2.3,1],hspace=0.08,left=0.115,right=0.985,top=0.84,bottom=0.2)
ax=fig.add_subplot(gs[0]); ax2=fig.add_subplot(gs[1],sharex=ax)
for a in (ax,ax2):
    a.set_facecolor(SURF)
    for sp in ('top','right'): a.spines[sp].set_visible(False)
    a.spines['left'].set_color(AXIS); a.spines['bottom'].set_color(AXIS)
# per-ride lines (gray) and overall median (blue)
ride_prof=W.groupby(['bin','ride'])['score'].median().unstack('ride').reindex(per.index)
for rd in ride_prof.columns:
    ax.plot(x,ride_prof[rd].rolling(2,min_periods=1).mean(),color=AXIS,lw=1,alpha=0.9,zorder=1)
ax.plot(x,med.values,color=BLUE,lw=2,zorder=3,solid_capstyle='round')
ax.axhline(1,color=GRID,lw=1,zorder=0)
ax.set_ylim(0,max(5.2,float(np.nanmax(med.values))*1.35))
ax.set_ylabel('Shake vs. a typical stretch (×)')
ax.yaxis.grid(True,color=GRID,lw=0.6); ax.set_axisbelow(True)
top5=Z.head(5)
placed=[]
for _,z in top5.sort_values('peak_bin').iterrows():
    px=(z.peak_bin*BIN+BIN/2)/1000; py=float(med.loc[z.peak_bin])
    ax.axvspan(z.start_m/1000,z.end_m/1000,color=CRIT,alpha=0.08,lw=0,zorder=0)
    ax2.axvspan(z.start_m/1000,z.end_m/1000,color=CRIT,alpha=0.08,lw=0,zorder=0)
    ax.scatter([px],[py],s=70,color=CRIT,edgecolor=SURF,linewidth=2,zorder=5)
    clash=any(abs(px-q)<0.45 for q in placed)
    placed.append(px)
    n_clash=sum(1 for q in placed[:-1] if abs(px-q)<0.8)
    if not clash: off,ha,va=(0,12),'center','bottom'
    elif n_clash==1: off,ha,va=(4,-58),'center','top'
    else: off,ha,va=(34,34),'left','bottom'
    ax.annotate(f"#{z['rank']}  {z.severity}×\n{z.rides_rough}/{z.rides_covering} rides",(px,py),
                xytext=off,textcoords='offset points',ha=ha,va=va,fontsize=8.5,color=INK,
                fontweight='bold' if z['rank']<=3 else 'normal',
                bbox=dict(boxstyle='round,pad=0.2',fc=SURF,ec='none',alpha=0.9) if clash else None,
                arrowprops=dict(arrowstyle='-',color=MUTED,lw=0.8) if clash else None)
# legend-ish direct labels
ax.text(0.995,0.97,'━ median of all 11 recordings',transform=ax.transAxes,color=BLUE,fontsize=9,va='top',ha='right')
ax.text(0.995,0.90,'━ each of the 5 train rides',transform=ax.transAxes,color=MUTED,fontsize=9,va='top',ha='right')
ax.text(0.995,0.83,'● top-5 hotspot (rank, severity, rides it showed up on)',transform=ax.transAxes,color=CRIT,fontsize=9,va='top',ha='right')
plt.setp(ax.get_xticklabels(),visible=False)
# ride strip: dot where that ride was in its top-10% roughest
rides=sorted(ride_hot.columns)
for i,rd in enumerate(rides):
    hb=ride_hot.index[ride_hot[rd].values]
    cov=ride_cov.index[ride_cov[rd].values]
    ax2.plot([(cov.min()*BIN)/1000,(cov.max()*BIN+BIN)/1000],[i,i],color=GRID,lw=6,solid_capstyle='round',zorder=1)
    ax2.scatter((hb*BIN+BIN/2)/1000,[i]*len(hb),s=14,color=INK2,zorder=2,linewidths=0)
ax2.set_yticks(range(len(rides)))
ax2.set_yticklabels([f"Ride {rd} · {ride_time[rd]} · {'WB' if ride_dir[rd]=='westbound' else 'EB'}" for rd in rides],fontsize=8.5,color=INK2)
ax2.set_ylim(len(rides)-0.4,-0.6)
ax2.tick_params(axis='y',length=0)
ax2.set_ylabel('')
ax2.text(0.0,1.03,'Dots = that ride’s roughest 10% of track. Columns of dots = the same spot, felt on every train.',transform=ax2.transAxes,fontsize=8.5,color=MUTED)
st=[(s['name'].replace(' Station','').replace(' E-Line',''),) for s in geo['stations']]
from trackscan import Line
L=Line(geo['shape'])
ss,_=L.project(np.array([s['lat'] for s in geo['stations']]),np.array([s['lon'] for s in geo['stations']]))
ticks=[(v/1000,s['name'].replace(' Station','').replace(' E-Line','').replace(' / Ethel Bradley','')) for s,v in zip(geo['stations'],ss) if lo-0.3<=v/1000<=hi+0.3]
ax2.set_xticks([t[0] for t in ticks]); ax2.set_xticklabels([t[1] for t in ticks],rotation=30,ha='right',fontsize=8.5,color=INK2)
ax2.set_xlim(lo-0.1,hi+0.1)
fig.text(0.115,0.95,'The same spots shake on every train',fontsize=17,fontweight='bold',color=INK)
fig.text(0.115,0.905,'Vertical vibration along the Metro E Line, Expo Park/USC → Culver City  ·  11 recordings on 5 separate trains, Sept 26  ·  speed-adjusted  ·  braking & accelerating removed',fontsize=10,color=INK2)
fig.text(0.115,0.03,'Method: phones flat on the train floor (phyphox, ~100 readings/sec + GPS) → 1–30 Hz vertical vibration per second → seconds where the train was braking,\naccelerating or stopped removed (|Δspeed| > 0.3 m/s² or within 10 s of a stop) → snapped to LA Metro’s E Line track shape → 25 m segments → compared across rides.',fontsize=8,color=MUTED)
fig.savefig(f'{OUT}/TrackScan_chart.png',dpi=160,facecolor=SURF)
print('saved')
