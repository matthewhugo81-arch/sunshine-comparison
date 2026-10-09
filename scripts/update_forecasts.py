"""Refresh complete 24-hour sunshine totals from explicit, common 00 UTC runs."""
from pathlib import Path
from datetime import datetime, timedelta, timezone
import argparse
import concurrent.futures
import json
import math
import os
import urllib.request
import urllib.parse
import urllib.error
import calendar

ROOT = Path(__file__).resolve().parents[1]
MODELS = [
    {'id':'ecmwf_ifs','name':'ECMWF IFS','resolution':'9 km','max_days':15,'provider':'ECMWF'},
    {'id':'gfs_global','name':'GFS','resolution':'~13 km','max_days':16,'provider':'NOAA'},
    {'id':'ukmo_global_deterministic_10km','name':'UKMO Global','resolution':'10 km','max_days':7,'provider':'UK Met Office'},
    {'id':'ukmo_uk_deterministic_2km','name':'UKMO UKV','resolution':'2 km','max_days':3,'provider':'UK Met Office'},
]
VARIABLES = ['sunshine_duration','shortwave_radiation','direct_radiation','diffuse_radiation',
             'direct_normal_irradiance','cloud_cover','cloud_cover_low','cloud_cover_mid',
             'cloud_cover_high','precipitation']
UNITS = {v: ('s' if v=='sunshine_duration' else '%' if v.startswith('cloud_cover') else
              'mm' if v=='precipitation' else 'W/m²') for v in VARIABLES}
QC_VERSION = '2026-10-09.1'

def finite(value):
    return not isinstance(value,bool) and isinstance(value,(float,int)) and math.isfinite(value)

def solar_window(date, latitude, longitude):
    """Approximate apparent sunrise/set UTC minutes, NOAA fractional-year equations.

    Used only as a generous physical bound and review screen, never to change sunshine.
    Source: https://gml.noaa.gov/grad/solcalc/solareqns.PDF
    """
    day=datetime.fromisoformat(date)
    gamma=2*math.pi/(366 if calendar.isleap(day.year) else 365)*(day.timetuple().tm_yday-1)
    eq=229.18*(.000075+.001868*math.cos(gamma)-.032077*math.sin(gamma)
               -.014615*math.cos(2*gamma)-.040849*math.sin(2*gamma))
    dec=(.006918-.399912*math.cos(gamma)+.070257*math.sin(gamma)-.006758*math.cos(2*gamma)
         +.000907*math.sin(2*gamma)-.002697*math.cos(3*gamma)+.00148*math.sin(3*gamma))
    lat=math.radians(latitude)
    arg=math.cos(math.radians(90.833))/(math.cos(lat)*math.cos(dec))-math.tan(lat)*math.tan(dec)
    half=math.degrees(math.acos(max(-1,min(1,arg))))*4
    noon=720-4*longitude-eq
    return noon-half,noon+half

def assess_day(hourly, date, latitude, longitude):
    """Reject physical failures; separately withhold conservative review flags.

    Cloud/rain screens are NOT validated error detectors or bias corrections. Thin
    cloud and showers can coexist with sunshine. Flagged values require review.
    """
    day=datetime.fromisoformat(date)
    bytime={t:{v:hourly[v][i] for v in VARIABLES} for i,t in enumerate(hourly['time'])}
    stamps=[(day+timedelta(hours=h)).isoformat(timespec='minutes') for h in range(1,25)]
    rows=[bytime.get(t,{}) for t in stamps]
    total=daily_total({t:r.get('sunshine_duration') for t,r in zip(stamps,rows)},date)
    if total is None:return None
    rise,setting=solar_window(date,latitude,longitude)
    daylight=(setting-rise)/60
    failures=[];reviews=[];evidence=[]
    if any(not finite(row.get(v)) for row in rows for v in VARIABLES):
        failures.append('Incomplete radiation/cloud checks')
    else:
        for h,(stamp,row) in enumerate(zip(stamps,rows),1):
            ghi,direct,diffuse=(row[k] for k in ['shortwave_radiation','direct_radiation','diffuse_radiation'])
            # 2 W/m² permits rounding/compression noise, not material negative diffuse.
            if direct>ghi+2 or min(ghi,direct,diffuse)<-2 or abs(ghi-direct-diffuse)>2:
                evidence.append({'time':stamp,'total_w_m2':ghi,'direct_w_m2':direct,'diffuse_w_m2':diffuse})
            if any(not 0<=row[v]<=100 for v in VARIABLES if v.startswith('cloud_cover')) or row['precipitation']<0 or row['direct_normal_irradiance']<-2:
                failures.append('Invalid cloud, rain or radiation range')
            # Ten-minute tolerance for approximate solar geometry and grid precision.
            possible=max(0,min(h*60,setting)-max((h-1)*60,rise))
            if row['sunshine_duration']>possible*60+600:
                failures.append('Sunshine outside the daylight window')
        if evidence:failures.append('Direct/diffuse radiation fails energy consistency')
    if total>daylight+1/6:failures.append('Sunshine exceeds astronomical daylight')
    result={'status':'withheld' if failures else 'experimental','reported_hours':round(total,5),
            'daylight_hours':round(daylight,3),'reasons':list(dict.fromkeys(failures)),
            'radiation_failures':evidence}
    if not failures or (len(failures)==1 and evidence):
        cloud_sum=low_sum=rain=weight_sum=conflict=0
        for h,(stamp,row) in enumerate(zip(stamps,rows),1):
            weight=max(0,min(h*60,setting)-max((h-1)*60,rise))/60
            if weight<=0:continue
            prev=bytime.get((day+timedelta(hours=h-1)).isoformat(timespec='minutes'),{})
            if not all(finite(prev.get(v)) for v in ['cloud_cover','cloud_cover_low']):
                result['reasons'].append('Incomplete daylight cloud checks');result['status']='withheld';return result
            # Cloud is instantaneous: average both bounds of the preceding-hour interval.
            cloud=(prev['cloud_cover']+row['cloud_cover'])/2
            low=(prev['cloud_cover_low']+row['cloud_cover_low'])/2
            cloud_sum+=cloud*weight;low_sum+=low*weight;weight_sum+=weight
            # Rain in an interval touching daylight is included in full, not treated as precise daylight timing.
            rain+=row['precipitation']
            if low>=80 and row['sunshine_duration']>=2700:conflict+=1
        cloud_mean=cloud_sum/weight_sum if weight_sum else 0
        low_mean=low_sum/weight_sum if weight_sum else 0
        fraction=total/daylight if daylight else 0
        if fraction>=.90 and cloud_mean>=25:
            reviews.append('Near-full daylight sunshine with substantial cloud: review required')
        if fraction>=.75 and rain>=1:
            reviews.append('High sunshine with rain in daylight intervals: review required')
        if conflict>=2:
            reviews.append('Several bright hours coincide with extensive low cloud: review required')
        result.update(daylight_cloud_percent=round(cloud_mean,1),daylight_low_cloud_percent=round(low_mean,1),
                      rain_in_daylight_intervals_mm=round(rain,2),low_cloud_conflict_hours=conflict)
        result['reasons'].extend(reviews)
        if reviews and not failures:result['status']='review'
    return result

def daily_total(hourly, date):
    """Use preceding-hour interval endpoints, requiring ALL 24 real values."""
    day=datetime.fromisoformat(date)
    values=[hourly.get((day+timedelta(hours=h)).isoformat(timespec='minutes')) for h in range(1,25)]
    if any(v is None for v in values): return None
    if any(isinstance(v,bool) or not isinstance(v,(float,int)) or not math.isfinite(v) or not 0<=v<=3600.01 for v in values):
        raise ValueError('Invalid hourly sunshine amount')
    return sum(values)/3600

def fetch(model, stations, run):
    params={
        'latitude':','.join(str(s['latitude']) for s in stations),
        'longitude':','.join(str(s['longitude']) for s in stations),
        'elevation':','.join('nan' for _ in stations),
        'models':model['id'],'hourly':','.join(VARIABLES),'timezone':'GMT',
        'run':run,'forecast_hours':model['max_days']*24+1,'cell_selection':'nearest',
    }
    key=os.environ.get('OPEN_METEO_API_KEY')
    endpoint='https://single-runs-api.open-meteo.com/v1/forecast'
    if key:
        endpoint='https://customer-single-runs-api.open-meteo.com/v1/forecast'
        params['apikey']=key
    req=urllib.request.Request(endpoint+'?'+urllib.parse.urlencode(params),headers={'User-Agent':'sunshine-comparison/1.0'})
    try:
        with urllib.request.urlopen(req,timeout=60) as response: result=json.load(response)
    except urllib.error.HTTPError as e:
        # Do not include URL or body: a commercial API key may be in the request.
        raise RuntimeError(f'{model["name"]}: provider returned HTTP {e.code}') from None
    if not isinstance(result,list) or len(result)!=len(stations):raise ValueError('Unexpected location count')
    for index,item in enumerate(result):
        if item.get('location_id',index)!=index:raise ValueError('Unexpected location order')
        if item.get('utc_offset_seconds')!=0:raise ValueError('Expected UTC data')
        for variable,unit in UNITS.items():
            if item['hourly_units'].get(variable)!=unit:raise ValueError(f'Unexpected {variable} units')
            if len(item['hourly']['time'])!=len(item['hourly'][variable]):raise ValueError('Mismatched hourly data')
        times=item['hourly']['time']
        expected=[(datetime.fromisoformat(run)+timedelta(hours=i)).isoformat(timespec='minutes') for i in range(len(times))]
        if times!=expected:raise ValueError('Unexpected run start or hourly timestamps')
        s=stations[index]
        km=111*math.hypot(item['latitude']-s['latitude'],(item['longitude']-s['longitude'])*math.cos(math.radians(s['latitude'])))
        if km>40:raise ValueError('Returned grid cell is too far from station')
    return result

def collect(stations,run):
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        futures=[pool.submit(fetch,m,stations,run) for m in MODELS]
        results=[];errors=[]
        for f in futures:
            try:results.append(f.result())
            except Exception as e:errors.append(str(e))
    if errors:raise RuntimeError('; '.join(errors))
    return results

def build_snapshot(stations,run,responses,now):
    start=datetime.fromisoformat(run).date()
    models=[]
    for model,locations in zip(MODELS,responses):
        daily={};quality={}
        for day in range(model['max_days']):
            date=(start+timedelta(days=day)).isoformat()
            checks=[assess_day(r['hourly'],date,r['latitude'],r['longitude']) for r in locations]
            # Retain the actual complete-data horizon, including days requiring review.
            # Each suspect station is null, never zero, and has a reason alongside it.
            if all(check is not None for check in checks):
                quality[date]=checks
                daily[date]=[c['reported_hours'] if c['status']=='experimental' else None for c in checks]
        if not daily:raise ValueError(f'{model["name"]}: no complete days')
        cells=[{'latitude':r['latitude'],'longitude':r['longitude']} for r in locations]
        models.append({**model,'run':run+'Z','daily':daily,'quality':quality,'grid_cells':cells,'available_through':max(daily)})
    today=now.date().isoformat()
    dates=sorted({date for m in models for date in m['daily'] if date>=today})
    if not dates:raise ValueError('No current/future complete days')
    return {'schema_version':2,'quality_version':QC_VERSION,'validation_status':'experimental; not observation-validated',
            'updated_at':now.isoformat(),'run':run+'Z','dates':dates,
            'period':'00:00–24:00 UTC','rounding':'nearest hour, halves up','models':models,
            'station_count':len(stations),'source':'Open-Meteo Single Runs API',
            'method':'Open-Meteo radiation-derived approximation: linear 60–180 W/m² DNI transition centred on 120 W/m², clipped to daylight. Hourly means cannot resolve intermittent sunshine.',
            'excluded_location':'RoI — Republic of Ireland: station or averaging definition not supplied.'}

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--run');args=parser.parse_args()
    stations=json.loads((ROOT/'data/stations.json').read_text(encoding='utf-8'))
    now=datetime.now(timezone.utc)
    candidates=[args.run] if args.run else [(now.date()-timedelta(days=d)).isoformat()+'T00:00' for d in range(2)]
    snapshot=None
    for run in candidates:
        try:
            responses=collect(stations,run)
            snapshot=build_snapshot(stations,run,responses,now)
            break
        except Exception as e:
            print(f'Run {run} unavailable: {e}',flush=True)
    if snapshot is None:raise SystemExit('No complete common run. Existing published forecast must be retained.')
    target=ROOT/'data/forecast.json'
    temp=target.with_suffix('.tmp')
    temp.write_text(json.dumps(snapshot,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
    temp.replace(target)
    raw={'run':run+'Z','retrieved_at':now.isoformat(),'models':[
        {'id':m['id'],'locations':r} for m,r in zip(MODELS,responses)]}
    raw_target=ROOT/'data/hourly.json';raw_temp=raw_target.with_suffix('.tmp')
    raw_temp.write_text(json.dumps(raw,ensure_ascii=False,separators=(',',':')),encoding='utf-8');raw_temp.replace(raw_target)
    print('Run:',snapshot['run'])
    for m in snapshot['models']:print(m['name'],len(m['daily']),'complete days; through',m['available_through'])

if __name__=='__main__':main()
