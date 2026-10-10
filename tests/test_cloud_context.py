"""All-model cloud use, time alignment, missing data and non-correction regressions."""
import copy
import importlib.util
import io
import json
from pathlib import Path
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

spec=importlib.util.spec_from_file_location('cloud_updater',Path(__file__).resolve().parents[1]/'scripts/update_forecasts.py')
u=importlib.util.module_from_spec(spec);spec.loader.exec_module(u)
DATE='2026-10-10'
RUN=DATE+'T00:00'

def sample(hours=25):
    start=datetime.fromisoformat(RUN)
    hourly={'time':[(start+timedelta(hours=i)).isoformat(timespec='minutes') for i in range(hours)]}
    for v in u.VARIABLES:hourly[v]=[0.0]*hours
    for v,value in zip(u.CLOUD_FIELDS,[65,15,35,55]):hourly[v]=[value]*hours
    return hourly

class CloudContext(unittest.TestCase):
    def context(self,hourly):return u.cloud_context(hourly,DATE,54,-2)

    def test_all_four_cloud_fields_are_computed(self):
        context=self.context(sample())
        self.assertEqual(context['cloud_fields_complete'],4)
        for name,value in zip(u.CLOUD_FIELDS.values(),[65,15,35,55]):
            self.assertEqual(context[name],value)
        self.assertNotEqual(context['daylight_cloud_percent'],15+35+55)

    def test_partial_sunrise_interval_is_integrated_not_full_hour_averaged(self):
        h=sample();h['cloud_cover']=[0]*25;h['cloud_cover'][7]=100
        with patch.object(u,'solar_window',return_value=(6*60+30,7*60)):
            context=self.context(h)
        self.assertEqual(context['daylight_cloud_percent'],75)
        self.assertEqual(context['cloud_coverage']['cloud_cover']['daylight_hours'],.5)

    def test_partial_sunset_interval_is_integrated(self):
        h=sample();h['cloud_cover']=[0]*25;h['cloud_cover'][7]=100
        with patch.object(u,'solar_window',return_value=(6*60,6*60+30)):
            self.assertEqual(self.context(h)['daylight_cloud_percent'],25)

    def test_night_cloud_cannot_inflate_daylight_average(self):
        h=sample();h['cloud_cover']=[100]*25
        for i in range(6,19):h['cloud_cover'][i]=0
        with patch.object(u,'solar_window',return_value=(6*60,18*60)):
            self.assertEqual(self.context(h)['daylight_cloud_percent'],0)

    def test_missing_rain_does_not_erase_cloud(self):
        h=sample();h['precipitation'][12]=None
        context=self.context(h)
        self.assertEqual(context['cloud_fields_complete'],4)
        self.assertNotIn('rain_in_daylight_intervals_mm',context)

    def test_missing_one_layer_does_not_erase_other_layers(self):
        h=sample();h['cloud_cover_mid'][12]=None
        c=self.context(h)
        self.assertNotIn('daylight_mid_cloud_percent',c)
        self.assertEqual(c['daylight_low_cloud_percent'],15)
        self.assertEqual(c['daylight_high_cloud_percent'],55)
        self.assertEqual(c['daylight_cloud_percent'],65)
        self.assertFalse(c['cloud_coverage']['cloud_cover_mid']['complete'])
        self.assertLess(c['cloud_coverage']['cloud_cover_mid']['coverage_percent'],100)
        self.assertEqual(c['cloud_fields_complete'],3)

    def test_absent_total_is_not_synthesised_from_layers(self):
        h=sample();del h['cloud_cover']
        c=self.context(h)
        self.assertNotIn('daylight_cloud_percent',c)
        self.assertEqual(c['cloud_fields_complete'],3)

    def test_invalid_cloud_is_not_clear_sky(self):
        for bad in [None,-1,101,True,float('nan'),float('inf'),'75']:
            with self.subTest(bad=bad):
                h=sample();h['cloud_cover_high'][12]=bad
                c=self.context(h)
                self.assertNotIn('daylight_high_cloud_percent',c)
                self.assertEqual(c['cloud_fields_complete'],3)

    def test_no_cloud_never_becomes_zero_cloud(self):
        h=sample()
        for v in u.CLOUD_FIELDS:del h[v]
        c=self.context(h)
        self.assertEqual(c['cloud_fields_complete'],0)
        for name in u.CLOUD_FIELDS.values():self.assertNotIn(name,c)

    def test_zero_cloud_is_valid(self):
        h=sample()
        for v in u.CLOUD_FIELDS:h[v]=[0]*25
        c=self.context(h)
        self.assertEqual(c['cloud_fields_complete'],4)
        for name in u.CLOUD_FIELDS.values():self.assertEqual(c[name],0)

    def test_optional_cloud_does_not_change_sunshine_or_status(self):
        h=sample();h['sunshine_duration'][12]=1800
        first=u.assess_day(h,DATE,54,-2)
        for v in u.CLOUD_FIELDS:h[v]=[100]*25
        second=u.assess_day(h,DATE,54,-2)
        h['cloud_cover_mid'][12]=None
        third=u.assess_day(h,DATE,54,-2)
        for assessment in [first,second,third]:
            self.assertEqual(assessment['reported_hours'],.5)
            self.assertEqual(assessment['status'],'experimental')
            self.assertEqual(assessment['reasons'],[])

    def test_withheld_sunshine_still_has_cloud_context(self):
        h=sample();h['direct_radiation'][12]=50;h['diffuse_radiation'][12]=-50
        c=u.assess_day(h,DATE,54,-2)
        self.assertEqual(c['status'],'withheld')
        self.assertEqual(c['cloud_fields_complete'],4)

    def test_low_and_medium_cloud_independently_trigger_review(self):
        for key in ['daylight_low_cloud_percent','daylight_mid_cloud_percent']:
            c={k:0 for k in u.CLOUD_FIELDS.values()};c[key]=90
            flags=u.cloud_review_flags(c,9,10)
            self.assertEqual(len(flags),1)
            self.assertIn('review only, no correction',flags[0])

    def test_high_cloud_is_context_not_an_opaque_cloud_rule(self):
        c=dict(zip(u.CLOUD_FIELDS.values(),[100,0,0,95]))
        flags=u.cloud_review_flags(c,9,10)
        self.assertEqual(len(flags),1)
        self.assertIn('High cloud dominates',flags[0])
        self.assertIn('optical thickness is unknown',flags[0])
        c['daylight_cloud_percent']=40
        self.assertEqual(u.cloud_review_flags(c,9,10),[])

    def test_missing_low_cloud_is_not_assumed_high_cloud_only(self):
        c={'daylight_cloud_percent':100,'daylight_high_cloud_percent':100}
        flags=u.cloud_review_flags(c,9,10)
        self.assertNotIn('High cloud dominates',flags[0])
        self.assertIn('Low missing',flags[0])

    def test_review_threshold_uses_sunshine_fraction_not_fixed_hours(self):
        c={'daylight_cloud_percent':100}
        self.assertEqual(u.cloud_review_flags(c,5,10),[])
        self.assertTrue(u.cloud_review_flags(c,5,6))

    def test_models_keep_separate_cloud_values_and_longer_cloud_horizon(self):
        responses=[]
        for index,model in enumerate(u.MODELS):
            h=sample(49)
            h['sunshine_duration'][25:]=[None]*24
            for layer in u.CLOUD_FIELDS:h[layer]=[10*(index+1)]*49
            responses.append([{'hourly':h,'latitude':54,'longitude':-2}])
        stations=[{'name':'Test','latitude':54,'longitude':-2}]
        snapshot=u.build_snapshot(stations,RUN,responses,datetime(2026,10,10,tzinfo=timezone.utc))
        for index,model in enumerate(snapshot['models']):
            self.assertEqual(model['id'],u.MODELS[index]['id'])
            self.assertEqual(model['available_through'],DATE)
            self.assertEqual(model['cloud_available_through'],'2026-10-11')
            self.assertNotIn('2026-10-11',model['daily'])
            for field in u.CLOUD_FIELDS.values():
                self.assertEqual(model['cloud_daily']['2026-10-11'][0][field],10*(index+1))
            self.assertEqual(model['quality'][DATE][0]['cloud_fields_complete'],4)

    def test_each_model_requests_all_cloud_layers_and_same_cycle(self):
        for model in u.MODELS:
            with self.subTest(model=model['name']):
                location={'latitude':54,'longitude':-2,'utc_offset_seconds':0,
                          'hourly':sample(),'hourly_units':u.UNITS}
                payload=json.dumps([location]).encode()
                with patch.object(u.urllib.request,'urlopen',return_value=io.BytesIO(payload)) as request:
                    u.fetch(model,[{'latitude':54,'longitude':-2}],RUN)
                    params=parse_qs(urlparse(request.call_args.args[0].full_url).query)
                self.assertEqual(params['models'],[model['id']])
                self.assertEqual(params['run'],[RUN])
                self.assertTrue(set(u.CLOUD_FIELDS).issubset(set(params['hourly'][0].split(','))))

    def test_missing_optional_array_does_not_fail_fetch(self):
        location={'latitude':54,'longitude':-2,'utc_offset_seconds':0,
                  'hourly':sample(),'hourly_units':copy.deepcopy(u.UNITS)}
        del location['hourly']['cloud_cover_high'];del location['hourly_units']['cloud_cover_high']
        with patch.object(u.urllib.request,'urlopen',return_value=io.BytesIO(json.dumps([location]).encode())):
            result=u.fetch(u.MODELS[0],[{'latitude':54,'longitude':-2}],RUN)
        self.assertNotIn('cloud_cover_high',result[0]['hourly'])

if __name__=='__main__':unittest.main()
