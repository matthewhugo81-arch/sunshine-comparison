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
from functools import lru_cache

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
QC_VERSION = '2026-10-09.3'
RADIATION_VARIABLES = ['shortwave_radiation','direct_radiation','diffuse_radiation',
                       'direct_normal_irradiance']

def finite(value):
    return not isinstance(value,bool) and isinstance(value,(float,int)) and math.isfinite(value)

def solar_terms(julian_day):
    """Solar declination (radians) and equation of time (minutes), NOAA/Meeus.

    Equations: https://gml.noaa.gov/grad/solcalc/main.js
    Full Gregorian date/Julian century, including year and leap days.
    """
    rad=math.radians;sin=math.sin;cos=math.cos
    t=(julian_day-2451545)/36525
    lon=(280.46646+t*(36000.76983+t*.0003032))%360
    anomaly=rad(357.52911+t*(35999.05029-.0001537*t))
    eccentricity=.016708634-t*(.000042037+.0000001267*t)
    centre=(sin(anomaly)*(1.914602-t*(.004817+.000014*t))
            +sin(2*anomaly)*(.019993-.000101*t)+sin(3*anomaly)*.000289)
    omega=rad(125.04-1934.136*t)
    apparent=rad(lon+centre-.00569-.00478*sin(omega))
    seconds=21.448-t*(46.8150+t*(.00059-t*.001813))
    obliquity=rad(23+(26+seconds/60)/60+.00256*cos(omega))
    declination=math.asin(sin(obliquity)*sin(apparent))
    y=math.tan(obliquity/2)**2;longitude=rad(lon)
    equation=4*math.degrees(y*sin(2*longitude)-2*eccentricity*sin(anomaly)
              +4*eccentricity*y*sin(anomaly)*cos(2*longitude)
              -.5*y*y*sin(4*longitude)-1.25*eccentricity**2*sin(2*anomaly))
    return declination,equation

@lru_cache(maxsize=8192)
def solar_window(date, latitude, longitude):
    """Apparent sunrise/set in UTC minutes for a UK/Ireland station and exact date.

    Flat sea-level horizon, 90.833° zenith (solar disc plus standard refraction),
    excludes twilight. Iterates solar coordinates to each event separately.
    Not intended for polar sites; fail explicitly if there is no daily rise/set.
    """
    if not -66<=latitude<=66 or not -180<=longitude<=180:
        raise ValueError('Solar calculation is scoped to non-polar sites')
    day=datetime.fromisoformat(date)
    jd=(day-datetime(2000,1,1)).total_seconds()/86400+2451544.5
    lat=math.radians(latitude)
    def event(sign):
        minute=720-4*longitude
        for _ in range(3):
            dec,eq=solar_terms(jd+minute/1440)
            arg=math.cos(math.radians(90.833))/(math.cos(lat)*math.cos(dec))-math.tan(lat)*math.tan(dec)
            if not -1<arg<1:raise ValueError('No daily sunrise/sunset at this latitude')
            minute=720-4*(longitude+sign*math.degrees(math.acos(arg)))-eq
        return minute
    return event(1),event(-1)

def daylight_details(date, latitude, longitude):
    rise,setting=solar_window(date,latitude,longitude)
    clock=lambda minute: f'{int(math.floor(minute+.5))//60:02d}:{int(math.floor(minute+.5))%60:02d}'
    return {'sunrise_utc':clock(rise),'sunset_utc':clock(setting),
            'daylight_hours':round((setting-rise)/60,6)}

def assess_day(hourly, date, latitude, longitude):
    """Check source physics, without cloud/rain thresholds or manufactured corrections.

    Cloud and rain are context only: their coincidence with sunshine is not a
    quantitative sunshine model. A passing result remains a provider estimate,
    not an observation-validated forecast or a native sunshine-duration field.
    """
    day=datetime.fromisoformat(date)
    bytime={t:{v:hourly[v][i] for v in VARIABLES} for i,t in enumerate(hourly['time'])}
    stamps=[(day+timedelta(hours=h)).isoformat(timespec='minutes') for h in range(1,25)]
    rows=[bytime.get(t,{}) for t in stamps]
    total=daily_total({t:r.get('sunshine_duration') for t,r in zip(stamps,rows)},date)
    if total is None:return None
    rise,setting=solar_window(date,latitude,longitude)
    daylight=(setting-rise)/60
    failures=[];evidence=[]
    if any(not finite(row.get(v)) for row in rows for v in RADIATION_VARIABLES):
        failures.append('Incomplete supporting radiation data')
    else:
        for h,(stamp,row) in enumerate(zip(stamps,rows),1):
            ghi,direct,diffuse=(row[k] for k in ['shortwave_radiation','direct_radiation','diffuse_radiation'])
            # 2 W/m² permits rounding/compression noise, not material negative diffuse.
            if direct>ghi+2 or min(ghi,direct,diffuse)<-2 or abs(ghi-direct-diffuse)>2:
                evidence.append({'time':stamp,'total_w_m2':ghi,'direct_w_m2':direct,'diffuse_w_m2':diffuse})
            if row['direct_normal_irradiance']<-2:
                failures.append('Invalid direct normal radiation range')
            # Two-minute tolerance for solar geometry/refraction, before display rounding.
            possible=max(0,min(h*60,setting)-max((h-1)*60,rise))
            if row['sunshine_duration']>possible*60+120:
                failures.append('Sunshine outside the daylight window')
        if evidence:failures.append('Direct/diffuse radiation fails energy consistency')
    if total>daylight+2/60:failures.append('Sunshine exceeds astronomical daylight')
    result={'status':'withheld' if failures else 'experimental','reported_hours':round(total,5),
            'daylight_hours':round(daylight,3),'reasons':list(dict.fromkeys(failures)),
            'radiation_failures':evidence,'review_flags':[]}
    if not failures or (len(failures)==1 and evidence):
        cloud_sum=low_sum=rain=weight_sum=0
        for h,(stamp,row) in enumerate(zip(stamps,rows),1):
            weight=max(0,min(h*60,setting)-max((h-1)*60,rise))/60
            if weight<=0:continue
            prev=bytime.get((day+timedelta(hours=h-1)).isoformat(timespec='minutes'),{})
            if (not all(finite(r.get(v)) and 0<=r[v]<=100
                        for r in [prev,row] for v in ['cloud_cover','cloud_cover_low'])
                    or not finite(row.get('precipitation')) or row['precipitation']<0):
                # Missing optional context cannot invalidate complete radiation data.
                return result
            # Cloud is instantaneous: average both bounds of the preceding-hour interval.
            cloud=(prev['cloud_cover']+row['cloud_cover'])/2
            low=(prev['cloud_cover_low']+row['cloud_cover_low'])/2
            cloud_sum+=cloud*weight;low_sum+=low*weight;weight_sum+=weight
            # Rain in an interval touching daylight is included in full, not treated as precise daylight timing.
            rain+=row['precipitation']
        cloud_mean=cloud_sum/weight_sum if weight_sum else 0
        low_mean=low_sum/weight_sum if weight_sum else 0
        result.update(daylight_cloud_percent=round(cloud_mean,1),daylight_low_cloud_percent=round(low_mean,1),
                      rain_in_daylight_intervals_mm=round(rain,2))
        # This is an advisory cross-variable diagnostic, NOT a sunshine correction.
        # Extensive thin/high cloud can coexist with bright sunshine.
        if result['status']=='experimental' and cloud_mean>=90 and total>=0.8*daylight:
            result['review_flags'].append(
                'High sunshine (>=80% of daylight) alongside >=90% mean total cloud; '
                'review radiation/cloud definition, including thin high cloud')
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
    if len(responses)!=len(MODELS) or any(len(r)!=len(stations) for r in responses):
        raise ValueError('Missing model or station response')
    start=datetime.fromisoformat(run).date()
    models=[]
    for model,locations in zip(MODELS,responses):
        daily={};quality={}
        for day in range(model['max_days']):
            date=(start+timedelta(days=day)).isoformat()
            checks=[assess_day(r['hourly'],date,r['latitude'],r['longitude']) for r in locations]
            # Require complete sunshine intervals at every station. Physical source
            # failures remain null; unsupported cloud/rain rules never suppress totals.
            if all(check is not None for check in checks):
                quality[date]=checks
                daily[date]=[c['reported_hours'] if c['status']=='experimental' else None for c in checks]
        if not daily:raise ValueError(f'{model["name"]}: no complete days')
        cells=[{'latitude':r['latitude'],'longitude':r['longitude']} for r in locations]
        models.append({**model,'run':run+'Z','daily':daily,'quality':quality,'grid_cells':cells,'available_through':max(daily)})
    today=now.date().isoformat()
    dates=sorted({date for m in models for date in m['daily'] if date>=today})
    if not dates:raise ValueError('No current/future complete days')
    daylight={date:[daylight_details(date,s['latitude'],s['longitude']) for s in stations] for date in dates}
    return {'schema_version':3,'quality_version':QC_VERSION,'validation_status':'experimental; not observation-validated',
            'quality_scope':'Physical consistency and completeness only; cloud/rain context does not alter sunshine.',
            'source_assessment':'https://github.com/matthewhugo81-arch/sunshine-comparison/blob/main/docs/source-assessment.md',
            'daylight':daylight,'daylight_method':'NOAA/Meeus apparent sunrise–sunset; station coordinates, exact Gregorian date, UTC, flat sea-level horizon; excludes twilight.',
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
