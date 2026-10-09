import unittest
from datetime import datetime,timedelta
import importlib.util
from pathlib import Path

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

if __name__=='__main__':unittest.main()
