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

    def test_rain_does_not_invent_a_sunshine_correction(self):
        result=self.assess(self.real[1])
        self.assertEqual(result['status'],'experimental')
        self.assertEqual(result['radiation_failures'],[])
        self.assertGreater(result['rain_in_daylight_intervals_mm'],5)
        self.assertEqual(result['reasons'],[])
        self.assertEqual(result['reported_hours'],10)

    def test_cloud_does_not_invent_a_sunshine_correction(self):
        result=self.assess(self.real[2])
        self.assertEqual(result['status'],'experimental')
        self.assertGreater(result['reported_hours']/result['daylight_hours'],.90)
        self.assertEqual(result['reasons'],[])

    def test_missing_radiation_cannot_pass(self):
        item=copy.deepcopy(self.real[2]);item['hourly']['direct_radiation'][12]=None
        result=self.assess(item)
        self.assertEqual(result['status'],'withheld')
        self.assertIn('Incomplete supporting radiation data',result['reasons'])

    def test_missing_optional_cloud_context_does_not_suppress_amount(self):
        item=copy.deepcopy(self.real[2]);item['hourly']['cloud_cover'][12]=None
        result=self.assess(item)
        self.assertEqual(result['status'],'experimental')
        self.assertNotIn('daylight_cloud_percent',result)

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

    def test_snapshot_preserves_physical_failures_without_cloud_rain_screens(self):
        stations=[{'name':r['station'],'latitude':r['latitude'],'longitude':r['longitude']} for r in self.real]
        snapshot=u.build_snapshot(stations,'2026-10-13T00:00',
                                  [self.real for _ in u.MODELS],datetime(2026,10,13,tzinfo=timezone.utc))
        self.assertEqual(snapshot['dates'],['2026-10-13'])
        for model in snapshot['models']:
            values=model['daily']['2026-10-13']
            self.assertIsNone(values[0])
            self.assertEqual(values[1],10)
            self.assertGreater(values[2],10.5)
            self.assertEqual(model['quality']['2026-10-13'][0]['reported_hours'],10)
        self.assertEqual(len(snapshot['daylight']['2026-10-13']),3)

    def test_missing_model_cannot_silently_shift_model_identity(self):
        with self.assertRaisesRegex(ValueError,'Missing model or station'):
            u.build_snapshot([], '2026-10-13T00:00', [], datetime.now(timezone.utc))

class DaylightGeometry(unittest.TestCase):
    def duration(self,date,lat,lon):
        rise,setting=u.solar_window(date,lat,lon)
        return setting-rise

    def test_independent_usno_sunrise_and_sunset(self):
        cases=json.loads((Path(__file__).parent/'fixtures/daylight-usno.json').read_text())
        for case in cases:
            with self.subTest(station=case['name'],date=case['date']):
                calculated=u.solar_window(case['date'],case['latitude'],case['longitude'])
                for value,key in zip(calculated,['sunrise_utc','sunset_utc']):
                    hour,minute=map(int,case[key].split(':'))
                    self.assertAlmostEqual(value,hour*60+minute,delta=1)

    def test_day_to_day_and_week_to_week_change(self):
        lengths=[self.duration(date,57.64574,-3.56202) for date in ['2026-10-13','2026-10-14','2026-10-20']]
        self.assertGreater(lengths[0],lengths[1])
        self.assertGreater(lengths[1],lengths[2])
        self.assertGreater(lengths[0]-lengths[2],20)

    def test_north_south_seasonal_reversal(self):
        for date,north_longer in [('2026-06-21',True),('2026-12-21',False)]:
            north=self.duration(date,57.64574,-3.56202);south=self.duration(date,49.208,-2.196)
            self.assertEqual(north>south,north_longer)

    def test_longitude_changes_solar_clock(self):
        east=u.solar_window('2026-10-13',53,0);west=u.solar_window('2026-10-13',53,-8)
        self.assertAlmostEqual(west[0]-east[0],32,delta=1)
        self.assertAlmostEqual(west[1]-east[1],32,delta=1)

    def test_clock_change_cannot_add_daylight(self):
        # UK clocks change on 25 October 2026; every calculation stays in UTC.
        before=self.duration('2026-10-24',51.47895,-.45158)
        after=self.duration('2026-10-25',51.47895,-.45158)
        self.assertTrue(0<before-after<5)

if __name__=='__main__':unittest.main()
