"""Tests verifying fixes for all six seeded defects in Track A."""
import tempfile
import unittest
from pathlib import Path
from ledger import storage, reporting, importing


class DefectRegressionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / 'test.sqlite3'
        self.db = storage.connect(self.db_path)
        storage.seed(self.db)

    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()

    def test_defect_1_mixed_validity_csv_processes_valid_rows(self):
        # Defect 1: A single invalid row must not abort the entire CSV import.
        csv_text = (
            "customer_id,invoice_number,amount,due_date\n"
            "HARBOR,MIX-1,100.00,2026-09-10\n"
            "UNKNOWN,MIX-2,200.00,2026-09-11\n"  # Invalid customer
            "MAPLE,MIX-3,300.00,2026-09-12\n"
        )
        result = importing.import_csv(self.db, csv_text, 'invoices')
        self.assertEqual(result['imported'], 2)
        self.assertEqual(result['skipped'], 0)
        self.assertEqual(result['rejected'], 1)
        self.assertEqual(len(result['errors']), 1)
        self.assertEqual(result['errors'][0]['line'], 3)
        self.assertIn('Unknown customer_id', result['errors'][0]['reason'])

        # Verify MIX-1 and MIX-3 are stored in DB
        inv1 = storage.invoice_by_key(self.db, 'HARBOR', 'MIX-1')
        inv3 = storage.invoice_by_key(self.db, 'MAPLE', 'MIX-3')
        self.assertIsNotNone(inv1)
        self.assertIsNotNone(inv3)

    def test_defect_2_invoice_deduplication_and_conflict_rejection(self):
        # Defect 2: Re-importing identical invoice should skip; conflicting details should reject.
        csv_first = (
            "customer_id,invoice_number,amount,due_date\n"
            "HARBOR,DEDUP-1,150.00,2026-09-15\n"
        )
        res1 = importing.import_csv(self.db, csv_first, 'invoices')
        self.assertEqual(res1['imported'], 1)

        # Re-import exact same invoice -> skipped
        res2 = importing.import_csv(self.db, csv_first, 'invoices')
        self.assertEqual(res2['imported'], 0)
        self.assertEqual(res2['skipped'], 1)
        self.assertEqual(res2['rejected'], 0)

        # Re-import same key with different amount -> rejected
        csv_conflict_amount = (
            "customer_id,invoice_number,amount,due_date\n"
            "HARBOR,DEDUP-1,999.00,2026-09-15\n"
        )
        res3 = importing.import_csv(self.db, csv_conflict_amount, 'invoices')
        self.assertEqual(res3['rejected'], 1)
        self.assertEqual(res3['errors'][0]['line'], 2)

        # Verify original invoice was preserved
        inv = storage.invoice_by_key(self.db, 'HARBOR', 'DEDUP-1')
        self.assertEqual(inv['amount'], 150.00)

    def test_defect_3_payment_matching_strictly_by_customer_and_invoice(self):
        # Defect 3: Payment with amount matching another invoice must NOT attach unless customer & invoice match.
        # Seed has MAPLE INV-201 with amount 600.00.
        # Import a payment of 600.00 for HARBOR NONEXISTENT.
        csv_payment = (
            "payment_id,customer_id,invoice_number,amount\n"
            "PAY-TEST-1,HARBOR,NONEXISTENT,600.00\n"
        )
        res = importing.import_csv(self.db, csv_payment, 'payments')
        self.assertEqual(res['imported'], 1)

        # Payment should remain unmatched (invoice_id is None)
        p = self.db.execute('SELECT * FROM payments WHERE payment_id=?', ('PAY-TEST-1',)).fetchone()
        self.assertIsNone(p['invoice_id'])

        # MAPLE INV-201 should still have 0 paid
        inv_maple = next(r for r in reporting.invoices(self.db) if r['invoice_number'] == 'INV-201')
        self.assertEqual(inv_maple['paid'], 0.00)
        self.assertEqual(inv_maple['balance'], 600.00)

    def test_defect_4_status_filtering_open_and_paid(self):
        # Defect 4: Filtering by open must return only open invoices; paid must return only paid.
        open_invs = reporting.invoices(self.db, status='open')
        paid_invs = reporting.invoices(self.db, status='paid')
        all_invs = reporting.invoices(self.db, status='all')

        self.assertEqual(len(all_invs), 6)
        self.assertEqual(len(open_invs), 5)
        self.assertEqual(len(paid_invs), 1)

        for inv in open_invs:
            self.assertEqual(inv['status'], 'open')
            self.assertGreater(inv['balance'], 0)

        for inv in paid_invs:
            self.assertEqual(inv['status'], 'paid')
            self.assertLessEqual(inv['balance'], 0)

        with self.assertRaises(ValueError):
            reporting.invoices(self.db, status='invalid_status')

    def test_defect_5_csv_export_money_precision_and_overpayment(self):
        # Defect 5: Money values like 19.99 must not truncate to 19.98.
        # Seeded NORTH INV-300 has amount 19.99, paid 10.00, balance 9.99.
        csv_out = reporting.export_csv(self.db)
        lines = [line.strip() for line in csv_out.strip().splitlines()]
        
        north_line = next(line for line in lines if 'NORTH,INV-300' in line)
        self.assertEqual(north_line, 'NORTH,INV-300,19.99,10.00,9.99,open')

        # Test overpayment export (balance should be negative with exact decimal)
        importing.import_csv(self.db, "payment_id,customer_id,invoice_number,amount\nOVER-1,NORTH,INV-301,150.00\n", 'payments')
        csv_out2 = reporting.export_csv(self.db)
        lines2 = [line.strip() for line in csv_out2.strip().splitlines()]
        over_line = next(line for line in lines2 if 'NORTH,INV-301' in line)
        self.assertEqual(over_line, 'NORTH,INV-301,100.00,150.00,-50.00,paid')

    def test_defect_6_import_result_structure_and_error_details(self):
        # Defect 6: API returns structured counts and errors for frontend consumption.
        csv_mixed = (
            "customer_id,invoice_number,amount,due_date\n"
            "HARBOR,OK-1,50.00,2026-09-01\n"
            "HARBOR,BAD-1,not-a-number,2026-09-01\n"
            "HARBOR,OK-1,50.00,2026-09-01\n"  # duplicate -> skipped
        )
        res = importing.import_csv(self.db, csv_mixed, 'invoices')
        self.assertEqual(res['imported'], 1)
        self.assertEqual(res['skipped'], 1)
        self.assertEqual(res['rejected'], 1)
        self.assertEqual(len(res['errors']), 1)
        self.assertEqual(res['errors'][0]['line'], 3)


if __name__ == '__main__':
    unittest.main()
