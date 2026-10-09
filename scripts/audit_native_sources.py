"""Read-only source investigation; never writes or substitutes daily forecasts.

Optional audit dependency: eccodes (pip install eccodes). Run sequentially because
some ecCodes Windows builds do not safely initialise definitions in parallel.
"""
import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]


def met_office_inventory(model, run):
    prefix=f'{model}/{run:%Y%m%dT%H%MZ}/'
    base='https://met-office-atmospheric-model-data.s3.eu-west-2.amazonaws.com/'
    params={'list-type':2,'prefix':prefix,'max-keys':1000}
    parameters={};count=0;pages=0
    while True:
        url=base+'?'+urllib.parse.urlencode(params)
        with urllib.request.urlopen(url,timeout=60) as response:
            tree=ET.fromstring(response.read())
        pages+=1
        for node in tree.findall('.//{*}Contents/{*}Key'):
            match=re.search(r'-PT(\d+)H(\d+)M-(.+)\.nc$',node.text)
            if match:
                hour,minute,name=match.groups()
                parameters.setdefault(name,[]).append(int(hour)+int(minute)/60)
            count+=1
        if tree.find('{*}IsTruncated').text=='false':break
        token=tree.find('{*}NextContinuationToken')
        if token is None or pages>=100:raise ValueError('Incomplete bucket inventory')
        params['continuation-token']=token.text
    if not count:raise ValueError(f'No objects for {prefix}')
    return {'source':base,'prefix':prefix,'complete_listing':True,'objects':count,
            'parameters':{k:sorted(v) for k,v in sorted(parameters.items())},
            'sunshine_name_matches':[k for k in parameters if re.search('sunshine|sunsd|sun_duration',k,re.I)]}


def gfs_record(run,hour,stations):
    import eccodes as ec
    url=(f'https://noaa-gfs-bdp-pds.s3.amazonaws.com/gfs.{run:%Y%m%d}/{run:%H}/atmos/'
         f'gfs.t{run:%H}z.pgrb2.0p25.f{hour:03d}')
    with urllib.request.urlopen(url+'.idx',timeout=60) as response:
        lines=response.read().decode().splitlines()
    matches=[i for i,line in enumerate(lines) if ':SUNSD:surface:' in line]
    if len(matches)!=1:raise ValueError('Expected one surface SUNSD record')
    i=matches[0]
    if i+1>=len(lines):raise ValueError('Cannot determine SUNSD byte range')
    start=int(lines[i].split(':')[1]);end=int(lines[i+1].split(':')[1])-1
    request=urllib.request.Request(url,headers={'Range':f'bytes={start}-{end}'})
    with urllib.request.urlopen(request,timeout=60) as response:
        if response.status!=206:raise ValueError('Server did not honour bounded byte range')
        data=response.read(end-start+2)
    if len(data)!=end-start+1 or data[:4]!=b'GRIB' or data[-4:]!=b'7777':
        raise ValueError('Incomplete GRIB record')
    gid=ec.codes_new_from_message(data)
    try:
        keys=['shortName','name','units','stepType','stepRange','dataDate','dataTime',
              'validityDate','validityTime','minimum','maximum','gridType','Ni','Nj']
        meta={key:ec.codes_get(gid,key) for key in keys}
        valid=run+timedelta(hours=hour)
        expected={'shortName':'SUNSD','units':'s','dataDate':int(run.strftime('%Y%m%d')),
                  'dataTime':int(run.strftime('%H%M')),'validityDate':int(valid.strftime('%Y%m%d')),
                  'validityTime':int(valid.strftime('%H%M')),'stepRange':str(hour)}
        if any(meta[k]!=v for k,v in expected.items()):raise ValueError('Unexpected GFS identity/time/units')
        points=[]
        for station in stations:
            point=dict(ec.codes_grib_find_nearest(gid,station['latitude'],station['longitude'])[0])
            if point['distance']>40:raise ValueError('GFS sample too far from station')
            points.append({'station':station['name'],**point})
        return {'forecast_hour':hour,'source':url,'index_record':lines[i],
                'byte_range':[start,end],'sha256':hashlib.sha256(data).hexdigest(),
                'metadata':meta,'points':points}
    finally:
        ec.codes_release(gid)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run',required=True,help='YYYY-MM-DDT00:00')
    parser.add_argument('--date',required=True,help='Day to inspect, YYYY-MM-DD')
    parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args()
    run=datetime.fromisoformat(args.run)
    day=datetime.fromisoformat(args.date)
    if run.hour or run.minute or run.tzinfo or day.tzinfo:raise ValueError('Use naive UTC midnight dates')
    first=int((day-run).total_seconds()/3600)
    if first<0 or first+24>384:raise ValueError('Date outside GFS forecast window')
    stations=json.loads((ROOT/'data/stations.json').read_text(encoding='utf-8'))
    result={'checked_at':datetime.now(timezone.utc).isoformat(),'run':args.run+'Z',
            'status':'investigation only; not a replacement sunshine forecast',
            'gfs_date':args.date,'gfs_records':[], 'met_office_inventories':{}}
    for hour in range(first+6,first+25,6):
        result['gfs_records'].append(gfs_record(run,hour,stations))
        print(f'Retrieved GFS SUNSD at +{hour} h (raw diagnostic, no daily conversion)',flush=True)
    for model in ['global-deterministic-10km','uk-deterministic-2km']:
        inv=met_office_inventory(model,run)
        result['met_office_inventories'][model]=inv
        print(model,len(inv['parameters']),'parameters; sunshine name matches:',inv['sunshine_name_matches'],flush=True)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')


if __name__=='__main__':main()
