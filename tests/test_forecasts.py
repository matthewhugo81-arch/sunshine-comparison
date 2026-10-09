import unittest
from datetime import datetime,timedelta,timezone
import importlib.util
from pathlib import Path
import json
import copy

spec=importlib.util.spec_from_file_location('updater',Path(__file__).resolve().parents[1]/'scripts/update_forecasts.py')
u=importlib.util.module_from_spec(spec);spec.loader.exec_module(u)

class DailyTotals(unittest.TestCase):
    def setUp(self):
        day=datetime(2026,10,9)
        self.hours={(day+timedelta(hours=h)).isoformat(timespec='minutes'):0 for h in range(25)}
        self.hours['2026-10-09T00:00']=None  # outside the valid day's accumulation
        self.hours['2026-10-09T12:00']=3600
        self.hours['2026-10-10T00:00']=1800
    def test_interval_endpoints(self):self.assertEqual(u.daily_total(self.hours,'2026-10-09'),1.5)
    def test_missing_is_not_zero(self):
        self.hours['2026-10-09T13:00']=None
        self.assertIsNone(u.daily_total(self.hours,'2026-10-09'))
    def test_end_of_model_range(self):
        del self.hours['2026-10-10T00:00']
        self.assertIsNone(u.daily_total(self.hours,'2026-10-09'))
    def test_zero_is_valid(self):
        self.hours={k:0 for k in self.hours}
        self.assertEqual(u.daily_total(self.hours,'2026-10-09'),0)
    def test_invalid_rejected(self):
        for bad in [-1,3601,float('nan')]:
            self.hours['2026-10-09T12:00']=bad
            with self.assertRaises(ValueError):u.daily_total(self.hours,'2026-10-09')

class QualityChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.real=json.loads((Path(__file__).parent/'fixtures/ifs-2026-10-13.json').read_text())

    def assess(self,entry):
        return u.assess_day(entry['hourly'],'2026-10-13',entry['latitude'],entry['longitude'])

    def test_real_kinloss_negative_diffuse_is_withheld(self):
        result=self.assess(self.real[0])
        self.assertEqual(result['status'],'withheld')
        self.assertEqual(result['reported_hours'],10)
        bad=result['radiation_failures']
        self.assertEqual(len(bad),2)
        self.assertEqual(bad[0]['diffuse_w_m2'],-30.5)

    def test_real_bishopton_cloud_rain_is_review_not_physical_failure(self):
        result=self.assess(self.real[1])
        self.assertEqual(result['status'],'review')
        self.assertEqual(result['radiation_failures'],[])
        self.assertGreater(result['rain_in_daylight_intervals_mm'],5)

    def test_cork_near_daylight_with_cloud_requires_review(self):
        result=self.assess(self.real[2])
        self.assertEqual(result['status'],'review')
        self.assertGreater(result['reported_hours']/result['daylight_hours'],.90)

    def test_missing_radiation_cannot_pass(self):
        item=copy.deepcopy(self.real[2]);item['hourly']['direct_radiation'][12]=None
        result=self.assess(item)
        self.assertEqual(result['status'],'withheld')
        self.assertIn('Incomplete radiation/cloud checks',result['reasons'])

    def test_night_sunshine_is_rejected(self):
        item=copy.deepcopy(self.real[2]);item['hourly']['sunshine_duration'][2]=3600
        result=self.assess(item)
        self.assertIn('Sunshine outside the daylight window',result['reasons'])

    def test_zero_day_is_retained_and_not_a_gap(self):
        item=copy.deepcopy(self.real[2])
        for v in u.VARIABLES:item['hourly'][v]=[0]*25
        result=self.assess(item)
        self.assertEqual(result['reported_hours'],0)
        self.assertEqual(result['status'],'experimental')

    def test_clear_day_is_not_arbitrarily_reduced(self):
        item=copy.deepcopy(self.real[2])
        for v in ['cloud_cover','cloud_cover_low','cloud_cover_mid','cloud_cover_high','precipitation']:
            item['hourly'][v]=[0]*25
        result=self.assess(item)
        self.assertEqual(result['status'],'experimental')
        self.assertGreater(result['reported_hours'],10.5)

    def test_missing_final_interval_excludes_day(self):
        item=copy.deepcopy(self.real[2]);item['hourly']['sunshine_duration'][-1]=None
        self.assertIsNone(self.assess(item))

    def test_daylight_season_and_latitude(self):
        oct_r,oct_s=u.solar_window('2026-10-13',57.65,-3.56)
        jun_r,jun_s=u.solar_window('2026-06-21',57.65,-3.56)
        self.assertTrue(10< (oct_s-oct_r)/60 <11)
        self.assertGreater((jun_s-jun_r)/60,17)

    def test_snapshot_keeps_review_as_null_not_zero_or_raw_amount(self):
        stations=[{'name':r['station']} for r in self.real]
        snapshot=u.build_snapshot(stations,'2026-10-13T00:00',
                                  [self.real for _ in u.MODELS],datetime(2026,10,13,tzinfo=timezone.utc))
        self.assertEqual(snapshot['dates'],['2026-10-13'])
        for model in snapshot['models']:
            self.assertEqual(model['daily']['2026-10-13'],[None,None,None])
            self.assertEqual(model['quality']['2026-10-13'][0]['reported_hours'],10)

if __name__=='__main__':unittest.main()
