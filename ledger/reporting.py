import csv
import io


def invoices(db, status='all', customer_id=None, sort_by=None):
    if status not in ('all', 'open', 'paid'):
        raise ValueError('status must be all, open or paid')
    query = '''
        SELECT i.id, i.customer_id, c.name AS customer_name, i.invoice_number,
               i.amount, i.due_date, COALESCE(SUM(p.amount), 0) AS paid
        FROM invoices i JOIN customers c ON c.customer_id=i.customer_id
        LEFT JOIN payments p ON p.invoice_id=i.id
    '''
    params = []
    if customer_id:
        query += ' WHERE i.customer_id = ?'
        params.append(customer_id)
    query += ' GROUP BY i.id ORDER BY i.id'
    data = db.execute(query, params).fetchall()
    result = []
    for row in data:
        item = dict(row)
        item['amount'] = round(float(item['amount']), 2)
        item['paid'] = round(float(item['paid']), 2)
        item['balance'] = round(item['amount'] - item['paid'], 2)
        item['status'] = 'paid' if item['balance'] <= 0 else 'open'
        result.append(item)
    if status != 'all':
        result = [r for r in result if r['status'] == status]
    if sort_by == 'due_date_asc':
        result.sort(key=lambda r: r['due_date'])
    elif sort_by == 'due_date_desc':
        result.sort(key=lambda r: r['due_date'], reverse=True)
    elif sort_by == 'balance_desc':
        result.sort(key=lambda r: r['balance'], reverse=True)
    elif sort_by == 'balance_asc':
        result.sort(key=lambda r: r['balance'])
    elif sort_by == 'amount_desc':
        result.sort(key=lambda r: r['amount'], reverse=True)
    elif sort_by == 'amount_asc':
        result.sort(key=lambda r: r['amount'])
    return result


def overview(db):
    rows = invoices(db)
    unmatched = [dict(r) for r in db.execute('''SELECT payment_id, customer_id,
        invoice_number, amount FROM payments WHERE invoice_id IS NULL ORDER BY payment_id''')]
    for u in unmatched:
        u['amount'] = round(float(u['amount']), 2)
    return {'invoices': rows, 'unmatched_payments': unmatched, 'summary': {
        'invoice_count': len(rows),
        'open_count': sum(1 for r in rows if r['status'] == 'open'),
        'outstanding': round(sum(r['balance'] for r in rows if r['balance'] > 0), 2),
    }}


def export_csv(db):
    output = io.StringIO(newline='')
    fields = ['customer_id', 'invoice_number', 'amount', 'paid', 'balance', 'status']
    writer = csv.DictWriter(output, fieldnames=fields, lineterminator='\r\n')
    writer.writeheader()
    for row in invoices(db):
        item = {
            'customer_id': row['customer_id'],
            'invoice_number': row['invoice_number'],
            'amount': f"{row['amount']:.2f}",
            'paid': f"{row['paid']:.2f}",
            'balance': f"{row['balance']:.2f}",
            'status': row['status'],
        }
        writer.writerow(item)
    return output.getvalue()
