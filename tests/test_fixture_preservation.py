"""Tests verifying preservation of the owner's existing register fixture and restart persistence."""
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from ledger import storage, reporting, importing


class FixturePreservationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / 'preserved.sqlite3'
        fixture_src = Path(__file__).resolve().parent.parent / 'fixtures' / 'existing-register.sqlite3'
        shutil.copy2(fixture_src, self.db_path)
        self.db = storage.connect(self.db_path)
        
        expected_path = Path(__file__).resolve().parent.parent / 'fixtures' / 'expected-records.json'
        with open(expected_path, 'r', encoding='utf-8') as f:
            self.expected = json.load(f)

    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()

    def test_existing_register_matches_expected_starting_state(self):
        overview = reporting.overview(self.db)
        summary = overview['summary']
        self.assertEqual(summary['invoice_count'], self.expected['summary']['invoice_count'])
        self.assertEqual(summary['open_count'], self.expected['summary']['open_count'])
        self.assertEqual(summary['outstanding'], float(self.expected['summary']['outstanding']))
        self.assertEqual(len(overview['unmatched_payments']), 1)
        
        unmatched = overview['unmatched_payments'][0]
        self.assertEqual(unmatched['payment_id'], 'KEEP-U1')
        self.assertEqual(unmatched['customer_id'], 'MAPLE')
        self.assertEqual(unmatched['invoice_number'], 'WAIT-900')
        self.assertEqual(unmatched['amount'], 33.33)

        # Check all 9 expected invoices in database
        invoices = reporting.invoices(self.db, status='all')
        self.assertEqual(len(invoices), 9)
        
        inv_map = {f"{r['customer_id']}_{r['invoice_number']}": r for r in invoices}
        for exp_inv in self.expected['invoices']:
            key = f"{exp_inv['customer_id']}_{exp_inv['invoice_number']}"
            self.assertIn(key, inv_map)
            actual = inv_map[key]
            self.assertEqual(actual['id'], exp_inv['id'])
            self.assertEqual(actual['amount'], float(exp_inv['amount']))
            self.assertEqual(actual['due_date'], exp_inv['due_date'])

        # Check all 5 expected payments in database
        db_payments = self.db.execute('SELECT * FROM payments ORDER BY payment_id').fetchall()
        self.assertEqual(len(db_payments), len(self.expected['payments']))
        pay_map = {r['payment_id']: r for r in db_payments}
        for exp_pay in self.expected['payments']:
            self.assertIn(exp_pay['payment_id'], pay_map)
            actual_pay = pay_map[exp_pay['payment_id']]
            self.assertEqual(actual_pay['customer_id'], exp_pay['customer_id'])
            self.assertEqual(actual_pay['invoice_number'], exp_pay['invoice_number'])
            self.assertEqual(round(actual_pay['amount'], 2), float(exp_pay['amount']))
            self.assertEqual(actual_pay['invoice_id'], exp_pay['invoice_id'])

    def test_new_imports_and_restart_persistence(self):
        # 1. Import new invoice
        new_inv_csv = (
            "customer_id,invoice_number,amount,due_date\n"
            "HARBOR,POST-KEEP-1,500.00,2026-09-25\n"
        )
        res_inv = importing.import_csv(self.db, new_inv_csv, 'invoices')
        self.assertEqual(res_inv['imported'], 1)

        # 2. Import payment towards new invoice
        new_pay_csv = (
            "payment_id,customer_id,invoice_number,amount\n"
            "POST-PAY-1,HARBOR,POST-KEEP-1,200.00\n"
        )
        res_pay = importing.import_csv(self.db, new_pay_csv, 'payments')
        self.assertEqual(res_pay['imported'], 1)

        # Verify updated totals: 10 invoices, 8 open, outstanding 3698.19 + 300.00 = 3998.19
        overview_mid = reporting.overview(self.db)
        self.assertEqual(overview_mid['summary']['invoice_count'], 10)
        self.assertEqual(overview_mid['summary']['open_count'], 8)
        self.assertEqual(overview_mid['summary']['outstanding'], 3998.19)

        # 3. Simulate application restart: close and reopen connection
        self.db.close()
        self.db = storage.connect(self.db_path)

        overview_after = reporting.overview(self.db)
        self.assertEqual(overview_after['summary']['invoice_count'], 10)
        self.assertEqual(overview_after['summary']['open_count'], 8)
        self.assertEqual(overview_after['summary']['outstanding'], 3998.19)

        # Verify new invoice row
        new_inv = storage.invoice_by_key(self.db, 'HARBOR', 'POST-KEEP-1')
        self.assertIsNotNone(new_inv)
        self.assertEqual(new_inv['amount'], 500.00)


if __name__ == '__main__':
    unittest.main()
