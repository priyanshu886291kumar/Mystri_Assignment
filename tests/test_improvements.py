"""Tests verifying the added customer filtering and due date / balance sorting improvements."""
import tempfile
import unittest
from pathlib import Path
from ledger import storage, reporting


class ImprovementTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / 'improvements.sqlite3'
        self.db = storage.connect(self.db_path)
        storage.seed(self.db)

    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()

    def test_customer_filtering(self):
        harbor_invoices = reporting.invoices(self.db, customer_id='HARBOR')
        self.assertEqual(len(harbor_invoices), 2)
        for inv in harbor_invoices:
            self.assertEqual(inv['customer_id'], 'HARBOR')

        maple_invoices = reporting.invoices(self.db, customer_id='MAPLE')
        self.assertEqual(len(maple_invoices), 2)
        for inv in maple_invoices:
            self.assertEqual(inv['customer_id'], 'MAPLE')

        north_invoices = reporting.invoices(self.db, customer_id='NORTH')
        self.assertEqual(len(north_invoices), 2)
        for inv in north_invoices:
            self.assertEqual(inv['customer_id'], 'NORTH')

    def test_due_date_sorting(self):
        asc = reporting.invoices(self.db, sort_by='due_date_asc')
        due_dates_asc = [r['due_date'] for r in asc]
        self.assertEqual(due_dates_asc, sorted(due_dates_asc))

        desc = reporting.invoices(self.db, sort_by='due_date_desc')
        due_dates_desc = [r['due_date'] for r in desc]
        self.assertEqual(due_dates_desc, sorted(due_dates_desc, reverse=True))

    def test_balance_sorting(self):
        desc = reporting.invoices(self.db, sort_by='balance_desc')
        balances_desc = [r['balance'] for r in desc]
        self.assertEqual(balances_desc, sorted(balances_desc, reverse=True))

        asc = reporting.invoices(self.db, sort_by='balance_asc')
        balances_asc = [r['balance'] for r in asc]
        self.assertEqual(balances_asc, sorted(balances_asc))

    def test_combined_status_customer_and_sort(self):
        # Open invoices for HARBOR sorted by balance descending
        res = reporting.invoices(self.db, status='open', customer_id='HARBOR', sort_by='balance_desc')
        # HARBOR has INV-100 (bal 1250, open) and INV-101 (bal 0, paid)
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0]['invoice_number'], 'INV-100')
        self.assertEqual(res[0]['balance'], 1250.00)


if __name__ == '__main__':
    unittest.main()
