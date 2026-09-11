"""Tests verifying edge cases, boundary conditions, and validation rules in Track A."""
import tempfile
import unittest
from pathlib import Path
from ledger import storage, reporting, importing


class EdgeCaseTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / 'edge.sqlite3'
        self.db = storage.connect(self.db_path)
        storage.seed(self.db)

    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()

    def test_utf8_bom_handling(self):
        csv_bom = '\ufeffcustomer_id,invoice_number,amount,due_date\nHARBOR,BOM-1,45.00,2026-09-10\n'
        res = importing.import_csv(self.db, csv_bom, 'invoices')
        self.assertEqual(res['imported'], 1)
        self.assertIsNotNone(storage.invoice_by_key(self.db, 'HARBOR', 'BOM-1'))

    def test_whitespace_trimming(self):
        csv_spaces = 'customer_id,invoice_number,amount,due_date\n  HARBOR  ,  TRIM-1  ,  75.50  ,  2026-09-12  \n'
        res = importing.import_csv(self.db, csv_spaces, 'invoices')
        self.assertEqual(res['imported'], 1)
        inv = storage.invoice_by_key(self.db, 'HARBOR', 'TRIM-1')
        self.assertIsNotNone(inv)
        self.assertEqual(inv['amount'], 75.50)
        self.assertEqual(inv['due_date'], '2026-09-12')

    def test_case_sensitive_customer_ids(self):
        # 'harbor' in lower case is invalid (must be 'HARBOR')
        csv_lower = 'customer_id,invoice_number,amount,due_date\nharbor,CASE-1,50.00,2026-09-10\n'
        res = importing.import_csv(self.db, csv_lower, 'invoices')
        self.assertEqual(res['rejected'], 1)
        self.assertIn('Unknown customer_id', res['errors'][0]['reason'])

    def test_overpayments_and_outstanding_total(self):
        # North INV-301 amount is 100.00. Pay 250.00 towards it.
        csv_overpay = 'payment_id,customer_id,invoice_number,amount\nOP-1,NORTH,INV-301,250.00\n'
        res = importing.import_csv(self.db, csv_overpay, 'payments')
        self.assertEqual(res['imported'], 1)

        inv = next(r for r in reporting.invoices(self.db) if r['invoice_number'] == 'INV-301')
        self.assertEqual(inv['paid'], 250.00)
        self.assertEqual(inv['balance'], -150.00)
        self.assertEqual(inv['status'], 'paid')

        # Total outstanding should NOT be reduced by negative balance of overpaid invoice
        # Seed outstanding was 3209.99 (which included INV-301 with 100.00).
        # When INV-301 becomes paid (balance <= 0), it simply contributes 0 to outstanding.
        # So new outstanding = 3209.99 - 100.00 = 3109.99.
        overview = reporting.overview(self.db)
        self.assertEqual(overview['summary']['outstanding'], 3109.99)

    def test_amount_boundary_values(self):
        # Max amount 10,000,000 is allowed
        csv_max = 'customer_id,invoice_number,amount,due_date\nHARBOR,MAX-1,10000000.00,2026-09-10\n'
        res_max = importing.import_csv(self.db, csv_max, 'invoices')
        self.assertEqual(res_max['imported'], 1)

        # > 10,000,000 is rejected
        csv_over_max = 'customer_id,invoice_number,amount,due_date\nHARBOR,MAX-2,10000000.01,2026-09-10\n'
        res_over_max = importing.import_csv(self.db, csv_over_max, 'invoices')
        self.assertEqual(res_over_max['rejected'], 1)

        # Zero amount rejected
        csv_zero = 'customer_id,invoice_number,amount,due_date\nHARBOR,ZERO-1,0.00,2026-09-10\n'
        res_zero = importing.import_csv(self.db, csv_zero, 'invoices')
        self.assertEqual(res_zero['rejected'], 1)

        # Negative amount in CSV rejected
        csv_neg = 'customer_id,invoice_number,amount,due_date\nHARBOR,NEG-1,-50.00,2026-09-10\n'
        res_neg = importing.import_csv(self.db, csv_neg, 'invoices')
        self.assertEqual(res_neg['rejected'], 1)

        # 3 decimal places rejected
        csv_3dec = 'customer_id,invoice_number,amount,due_date\nHARBOR,DEC-1,50.123,2026-09-10\n'
        res_3dec = importing.import_csv(self.db, csv_3dec, 'invoices')
        self.assertEqual(res_3dec['rejected'], 1)

    def test_empty_data_rows_with_valid_header(self):
        csv_empty = 'customer_id,invoice_number,amount,due_date\n'
        res = importing.import_csv(self.db, csv_empty, 'invoices')
        self.assertEqual(res['imported'], 0)
        self.assertEqual(res['skipped'], 0)
        self.assertEqual(res['rejected'], 0)
        self.assertEqual(res['errors'], [])

    def test_invalid_header_raises_error(self):
        csv_bad_header = 'wrong,header,row\n1,2,3\n'
        with self.assertRaises(ValueError):
            importing.import_csv(self.db, csv_bad_header, 'invoices')

    def test_payment_deduplication_and_conflict(self):
        # Import initial payment
        csv_p1 = 'payment_id,customer_id,invoice_number,amount\nP-DEDUP-1,HARBOR,INV-100,50.00\n'
        res1 = importing.import_csv(self.db, csv_p1, 'payments')
        self.assertEqual(res1['imported'], 1)

        # Re-import identical payment -> skipped
        res2 = importing.import_csv(self.db, csv_p1, 'payments')
        self.assertEqual(res2['skipped'], 1)

        # Re-import same payment_id with different amount -> rejected
        csv_conflict = 'payment_id,customer_id,invoice_number,amount\nP-DEDUP-1,HARBOR,INV-100,90.00\n'
        res3 = importing.import_csv(self.db, csv_conflict, 'payments')
        self.assertEqual(res3['rejected'], 1)


if __name__ == '__main__':
    unittest.main()
