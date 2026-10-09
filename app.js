'use strict';
const NS='http://www.w3.org/2000/svg';
const $=id=>document.getElementById(id);
let forecast,stations,coastline;
const dateLabel=date=>new Intl.DateTimeFormat('en-GB',{weekday:'short',day:'numeric',month:'short',year:'numeric',timeZone:'UTC'}).format(new Date(`${date}T12:00:00Z`));
const timeLabel=time=>new Intl.DateTimeFormat('en-GB',{day:'numeric',month:'short',hour:'2-digit',minute:'2-digit',hourCycle:'h23',timeZone:'UTC'}).format(new Date(time))+' UTC';
const hours=value=>Number.isFinite(value)?String(Math.floor(value+.5)):'—';
const shownModels=()=>forecast.models.filter(m=>$('model-select').value==='all'||m.id===$('model-select').value);
const available=(m,date)=>Array.isArray(m.daily[date])&&m.daily[date].length===stations.length&&m.daily[date].every(v=>v===null||Number.isFinite(v));
const assessment=(m,date,i)=>m.quality[date][i];
const valueLabel=(m,date,i)=>Number.isFinite(m.daily[date][i])?hours(m.daily[date][i]):'Review';
const reasonLabel=(m,date,i)=>assessment(m,date,i).reasons.join('; ')||'Experimental estimate; no automated flag. Not validated against observations.';
function element(tag,attrs={},text){const e=document.createElementNS(NS,tag);Object.entries(attrs).forEach(([k,v])=>e.setAttribute(k,v));if(text!==undefined)e.textContent=text;return e;}
function html(tag,cls,text){const e=document.createElement(tag);if(cls)e.className=cls;if(text!==undefined)e.textContent=text;return e;}

function buildDates(preferred){
  const models=shownModels();
  const dates=forecast.dates.filter(date=>models.some(m=>available(m,date)));
  $('forecast-date').replaceChildren(...dates.map(date=>{const o=document.createElement('option');o.value=date;o.textContent=dateLabel(date);return o;}));
  $('forecast-date').value=dates.includes(preferred)?preferred:dates.filter(d=>d<=preferred).at(-1)||dates[0];
}
function makeMap(model,date){
  const svg=element('svg',{xmlns:NS,viewBox:'0 0 1015 1185',class:'map-svg',role:'img','aria-label':`${model.name} sunshine hours for ${dateLabel(date)}`});
  svg.append(element('title',{},`${model.name} · ${dateLabel(date)} · sunshine hours`));
  svg.append(element('rect',{width:1015,height:1185,fill:'#c9d2db'}));
  const land=element('g',{fill:'#263747',stroke:'#526675','stroke-width':.65});
  coastline.forEach(d=>land.append(element('path',{d})));svg.append(land);
  stations.forEach((s,i)=>{
    const value=model.daily[date][i],label=valueLabel(model,date,i);const [x,y]=s.point,[lx,ly]=s.label;
    const name=$('label-select').value==='region'?s.region:s.short;
    const width=Math.max(Number.isFinite(value)?68:84,name.length*7.9+18);
    const g=element('g',{class:'station-marker',tabindex:'0','aria-label':`${s.name}, ${s.region}: ${label}${Number.isFinite(value)?' hours':''}. ${reasonLabel(model,date,i)}`});
    g.append(element('title',{},`${s.name} · ${s.region}\n${label}${Number.isFinite(value)?' sunshine hours':''}\n${reasonLabel(model,date,i)}\n${model.name} · ${dateLabel(date)}`));
    g.append(element('path',{d:`M${x},${y}L${lx},${ly}`,stroke:'#8295a2','stroke-width':1.4,fill:'none'}));
    g.append(element('circle',{cx:x,cy:y,r:3.4,fill:'#fff',stroke:'#172936','stroke-width':1}));
    g.append(element('rect',{x:lx-width/2,y:ly-33,width,height:65,rx:5,fill:'#172936',stroke:'#5c7282','stroke-width':1}));
    g.append(element('text',{x:lx,y:ly-1,'text-anchor':'middle',fill:Number.isFinite(value)?'#ffc857':'#ecb9a5','font-size':Number.isFinite(value)?40:20,'font-weight':700,'font-family':'Arial, sans-serif'},label));
    g.append(element('text',{x:lx,y:ly+21,'text-anchor':'middle',fill:'#e6edf3','font-size':14,'font-family':'Arial, sans-serif'},name));
    svg.append(g);
  });
  return svg;
}
async function savePNG(svg,model,date,button){
  button.disabled=true;button.textContent='Saving…';
  let url;
  try{
    const documentSVG=element('svg',{xmlns:NS,width:1218,height:1640,viewBox:'0 0 1015 1367'});
    documentSVG.append(element('rect',{width:1015,height:1367,fill:'#f3f5f6'}));
    documentSVG.append(element('text',{x:25,y:43,fill:'#172d3b','font-size':27,'font-weight':700,'font-family':'Arial, sans-serif'},`${model.name} | Experimental sunshine hours`));
    documentSVG.append(element('text',{x:25,y:74,fill:'#526577','font-size':18,'font-family':'Arial, sans-serif'},`${dateLabel(date)} · 00–24 UTC · nearest hour`));
    const copy=svg.cloneNode(true);copy.setAttribute('y','100');copy.setAttribute('width','1015');copy.setAttribute('height','1185');documentSVG.append(copy);
    documentSVG.append(element('text',{x:25,y:1310,fill:'#526577','font-size':14,'font-family':'Arial, sans-serif'},`Run: ${timeLabel(model.run)} · Review = withheld · Not observation-validated`));
    documentSVG.append(element('text',{x:25,y:1340,fill:'#526577','font-size':13,'font-family':'Arial, sans-serif'},`${model.provider} via Open-Meteo · Map: Natural Earth · CC BY-SA 4.0`));
    const blob=new Blob([new XMLSerializer().serializeToString(documentSVG)],{type:'image/svg+xml;charset=utf-8'});url=URL.createObjectURL(blob);
    const image=new Image();image.src=url;await image.decode();
    const canvas=document.createElement('canvas');canvas.width=1218;canvas.height=1640;canvas.getContext('2d').drawImage(image,0,0);
    const png=await new Promise(resolve=>canvas.toBlob(resolve,'image/png'));if(!png)throw Error('Image export failed');
    const download=URL.createObjectURL(png);const a=document.createElement('a');a.href=download;a.download=`sunshine-${model.id}-${date}.png`;a.click();setTimeout(()=>URL.revokeObjectURL(download),10000);
  }catch(e){$('alert').textContent='The image could not be saved. Please try again.';$('alert').hidden=false;console.error(e);}
  finally{if(url)URL.revokeObjectURL(url);button.disabled=false;button.textContent='Save PNG';}
}
function render(){
  const date=$('forecast-date').value;const models=shownModels();const count=models.filter(m=>available(m,date)).length;
  const withheld=models.reduce((n,m)=>n+(available(m,date)?m.daily[date].filter(v=>v===null).length:0),0);
  $('day-title').textContent=dateLabel(date);$('coverage').textContent=`${count} of ${models.length} feeds · ${withheld} station values withheld`;
  const select=$('forecast-date');$('previous').disabled=select.selectedIndex===0;$('next').disabled=select.selectedIndex===select.options.length-1;
  $('maps').classList.toggle('single',models.length===1);$('maps').replaceChildren();
  models.forEach(model=>{
    const card=html('article','map-card'),header=html('div','card-header'),heading=html('div');
    heading.append(html('h3','',model.name),html('p','',`${model.resolution} grid · through ${dateLabel(model.available_through)}`));header.append(heading);card.append(header);
    if(available(model,date)){
      const svg=makeMap(model,date),button=html('button','download','Save PNG');button.setAttribute('aria-label',`Save ${model.name} map as PNG`);button.addEventListener('click',()=>savePNG(svg,model,date,button));header.append(button);card.append(svg);
      const footer=html('div','card-footer');footer.append(html('span','','Experimental · Review = withheld'),html('span','',`Run: ${timeLabel(model.run)}`));card.append(footer);
    }else{
      const empty=html('div','unavailable');empty.append(html('span','empty-icon','◷'),html('strong','','Not available for this date'),html('p','',`Complete sunshine data for ${model.name} ends on ${dateLabel(model.available_through)}.`));card.append(empty);
    }
    $('maps').append(card);
  });
  const table=$('station-table'),thead=table.querySelector('thead'),tbody=table.querySelector('tbody');thead.replaceChildren();tbody.replaceChildren();
  const header=html('tr');['Station','Region',...models.map(m=>m.name)].forEach((name,i)=>{const th=html('th',i>=2?'number':'',name);th.scope='col';header.append(th);});thead.append(header);
  stations.forEach((station,i)=>{const row=html('tr');row.append(html('td','',station.name),html('td','region',station.region));models.forEach(model=>{const valid=available(model,date),review=valid&&model.daily[date][i]===null,td=html('td','number'+(valid?'':' missing')+(review?' review':''),valid?valueLabel(model,date,i):'—');if(!valid)td.setAttribute('aria-label','No complete source data');else td.title=reasonLabel(model,date,i);row.append(td);});tbody.append(row);});
  $('quality-summary').textContent=`Data checks and supporting forecasts · ${withheld} values withheld`;
  const qbody=$('quality-table').querySelector('tbody');qbody.replaceChildren();
  models.filter(m=>available(m,date)).forEach(model=>stations.forEach((station,i)=>{
    const q=assessment(model,date,i),row=html('tr'),format=(v,d=1)=>Number.isFinite(v)?v.toFixed(d):'—';
    const values=[`${station.name} / ${model.name}`,format(q.reported_hours,2),format(q.daylight_hours,2),`${format(q.daylight_cloud_percent,0)}% / ${format(q.daylight_low_cloud_percent,0)}%`,format(q.rain_in_daylight_intervals_mm,2),q.status==='experimental'?'Experimental; no automated flag':`${q.status==='withheld'?'Data failure':'Review screen'}: ${q.reasons.join('; ')}`];
    values.forEach((v,j)=>{const td=html('td',j===5?'check-reason':'',v);row.append(td);});qbody.append(row);
  }));
  const url=new URL(location.href);url.searchParams.set('date',date);url.searchParams.set('model',$('model-select').value);history.replaceState(null,'',url);
}
async function init(){
  try{
    [forecast,stations,coastline]=await Promise.all(['data/forecast.json','data/stations.json','assets/coastline.json'].map(async path=>{const r=await fetch(path,{cache:'no-cache'});if(!r.ok)throw Error(`Unable to load ${path}`);return r.json();}));
    if(forecast.schema_version!==2||forecast.station_count!==stations.length||!forecast.dates.length)throw Error('Quality-checked forecast data is incomplete');
    const params=new URLSearchParams(location.search);
    forecast.models.forEach(model=>{const o=document.createElement('option');o.value=model.id;o.textContent=model.name;$('model-select').append(o);});
    if(forecast.models.some(m=>m.id===params.get('model')))$('model-select').value=params.get('model');
    buildDates(params.get('date')||forecast.dates[0]);$('forecast-date').disabled=false;$('model-select').disabled=false;
    $('run-info').textContent=`Common forecast run: ${timeLabel(forecast.run)}`;$('updated-info').textContent=`Retrieved: ${timeLabel(forecast.updated_at)}`;
    if(Date.now()-Date.parse(forecast.updated_at)>24*3600000||Date.now()-Date.parse(forecast.run)>40*3600000){$('alert').textContent='These forecasts may be out of date. Check the run and update times above before use.';$('alert').hidden=false;}
    $('forecast-date').addEventListener('change',render);$('model-select').addEventListener('change',()=>{buildDates($('forecast-date').value);render();});$('label-select').addEventListener('change',render);
    ['previous','next'].forEach((id,index)=>$(id).addEventListener('click',()=>{$('forecast-date').selectedIndex+=index===0?-1:1;render();}));render();
  }catch(e){$('day-title').textContent='Forecasts could not be loaded';$('run-info').textContent='';$('alert').textContent='Please reload the page. If the problem persists, the forecast update may be temporarily unavailable.';$('alert').hidden=false;console.error(e);}
}
init();
