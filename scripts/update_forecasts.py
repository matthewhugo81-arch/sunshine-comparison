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

ROOT = Path(__file__).resolve().parents[1]
MODELS = [
    {'id':'ecmwf_ifs','name':'ECMWF IFS','resolution':'9 km','max_days':15,'provider':'ECMWF'},
    {'id':'gfs_global','name':'GFS','resolution':'~13 km','max_days':16,'provider':'NOAA'},
    {'id':'ukmo_global_deterministic_10km','name':'UKMO Global','resolution':'10 km','max_days':7,'provider':'UK Met Office'},
    {'id':'ukmo_uk_deterministic_2km','name':'UKMO UKV','resolution':'2 km','max_days':3,'provider':'UK Met Office'},
]

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
        'models':model['id'],'hourly':'sunshine_duration','timezone':'GMT',
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
        if item['hourly_units']['sunshine_duration']!='s':raise ValueError('Expected sunshine in seconds')
        if len(item['hourly']['time'])!=len(item['hourly']['sunshine_duration']):raise ValueError('Mismatched hourly data')
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
        station_hours=[dict(zip(r['hourly']['time'],r['hourly']['sunshine_duration'])) for r in locations]
        daily={}
        for day in range(model['max_days']):
            date=(start+timedelta(days=day)).isoformat()
            totals=[daily_total(hours,date) for hours in station_hours]
            # Publish a model/day only if every named station has all 24 hours.
            if all(v is not None for v in totals): daily[date]=totals
        if not daily:raise ValueError(f'{model["name"]}: no complete days')
        cells=[{'latitude':r['latitude'],'longitude':r['longitude']} for r in locations]
        models.append({**model,'run':run+'Z','daily':daily,'grid_cells':cells,'available_through':max(daily)})
    today=now.date().isoformat()
    dates=sorted({date for m in models for date in m['daily'] if date>=today})
    if not dates:raise ValueError('No current/future complete days')
    return {'schema_version':1,'updated_at':now.isoformat(),'run':run+'Z','dates':dates,
            'period':'00:00–24:00 UTC','rounding':'nearest hour, halves up','models':models,
            'station_count':len(stations),'source':'Open-Meteo Single Runs API',
            'method':'Radiation-derived sunshine duration; direct normal irradiance threshold 120 W/m².',
            'excluded_location':'RoI — Republic of Ireland: station or averaging definition not supplied.'}

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--run');args=parser.parse_args()
    stations=json.loads((ROOT/'data/stations.json').read_text(encoding='utf-8'))
    now=datetime.now(timezone.utc)
    candidates=[args.run] if args.run else [(now.date()-timedelta(days=d)).isoformat()+'T00:00' for d in range(2)]
    snapshot=None
    for run in candidates:
        try:
            snapshot=build_snapshot(stations,run,collect(stations,run),now)
            break
        except Exception as e:
            print(f'Run {run} unavailable: {e}',flush=True)
    if snapshot is None:raise SystemExit('No complete common run. Existing published forecast must be retained.')
    target=ROOT/'data/forecast.json'
    temp=target.with_suffix('.tmp')
    temp.write_text(json.dumps(snapshot,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
    temp.replace(target)
    print('Run:',snapshot['run'])
    for m in snapshot['models']:print(m['name'],len(m['daily']),'complete days; through',m['available_through'])

if __name__=='__main__':main()
