import sys,tempfile,unittest
from pathlib import Path
from datetime import date
sys.path.insert(0,'scripts')
from archive_reports import archive
class ArchiveTests(unittest.TestCase):
    def test_dates_retention_and_metrics(self):
        with tempfile.TemporaryDirectory() as d:
            r=Path(d);(r/'basketbol').mkdir();(r/'basketbol/basketbol.html').write_text("<div class='day-title'>2026-10-17</div>")
            for day in ['2026-10-16','2026-10-17','2026-10-18']:
                p=r/'raporlar'/day;p.mkdir(parents=True);(p/'custom.html').write_text(day)
                p=r/'deney/reports'/day;p.mkdir(parents=True);(p/'futbol-yeni.html').write_text(day);(p/'stability-evaluation.json').write_text('{}')
            archive(r,date(2026,10,18))
            self.assertFalse((r/'raporlar/2026-10-16').exists())
            self.assertFalse((r/'deney/reports/2026-10-16/futbol-yeni.html').exists())
            self.assertTrue((r/'deney/reports/2026-10-16/stability-evaluation.json').exists())
            self.assertTrue((r/'raporlar/2026-10-17/basketbol.html').exists())
            self.assertFalse((r/'raporlar/2026-10-18/basketbol.html').exists())
            self.assertTrue((r/'raporlar/2026-10-18/futbol-yeni.html').exists())
    def test_unknown_date_is_not_assigned_to_today(self):
        with tempfile.TemporaryDirectory() as d:
            r=Path(d);(r/'futbol').mkdir();(r/'futbol/futbol.html').write_text('<body>no verified date</body>')
            self.assertEqual(archive(r,date(2026,10,18)),[])
