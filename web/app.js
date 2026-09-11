const currency = new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR' });
const money = n => currency.format(n);
const text = (tag, value, className = '') => {
  const node = document.createElement(tag);
  node.textContent = value;
  node.className = className;
  return node;
};

async function refresh() {
  const status = document.querySelector('#status').value;
  const customer = document.querySelector('#customer')?.value || '';
  const sortBy = document.querySelector('#sort-by')?.value || '';

  let invoiceUrl = `/api/invoices?status=${encodeURIComponent(status)}`;
  if (customer) invoiceUrl += `&customer_id=${encodeURIComponent(customer)}`;
  if (sortBy) invoiceUrl += `&sort_by=${encodeURIComponent(sortBy)}`;

  const responses = await Promise.all([fetch('/api/overview'), fetch(invoiceUrl)]);
  if (responses.some(r => !r.ok)) throw new Error('Could not refresh the register.');
  const [data, rows] = await Promise.all(responses.map(r => r.json()));
  document.querySelector('#invoice-count').textContent = data.summary.invoice_count;
  document.querySelector('#open-count').textContent = data.summary.open_count;
  document.querySelector('#outstanding').textContent = money(data.summary.outstanding);
  const body = document.querySelector('#invoices');
  body.replaceChildren();
  if (rows.length === 0) {
    const emptyRow = document.createElement('tr');
    const emptyCell = document.createElement('td');
    emptyCell.colSpan = 7;
    emptyCell.textContent = 'No invoices found matching the selected filters.';
    emptyCell.style.textAlign = 'center';
    emptyCell.style.color = '#72818a';
    emptyCell.style.padding = '20px';
    emptyRow.append(emptyCell);
    body.append(emptyRow);
  } else {
    rows.forEach(r => {
      const row = document.createElement('tr');
      [r.customer_name, r.invoice_number, r.due_date].forEach(v => row.append(text('td', v)));
      [r.amount, r.paid, r.balance].forEach(v => row.append(text('td', money(v), 'number')));
      const tdStatus = document.createElement('td');
      tdStatus.append(text('span', r.status, `status-pill ${r.status}`));
      row.append(tdStatus);
      body.append(row);
    });
  }
  const unmatched = document.querySelector('#unmatched');
  unmatched.replaceChildren(...data.unmatched_payments.map(p => text('li', `${p.payment_id} · ${p.customer_id} / ${p.invoice_number} · ${money(p.amount)}`)));
  if (!data.unmatched_payments.length) unmatched.append(text('li', 'No unmatched payments.'));
  document.querySelector('#page-error').textContent = '';
}

async function submitImport(form) {
  const feedback = form.querySelector('.feedback');
  const button = form.querySelector('button');
  const fileInput = form.querySelector('input');
  button.disabled = true;
  feedback.textContent = 'Importing…';
  feedback.className = 'feedback';
  try {
    if (!fileInput.files || !fileInput.files.length) {
      throw new Error('Please select a CSV file first.');
    }
    const csv = await fileInput.files[0].text();
    const res = await fetch(`/api/import?kind=${form.dataset.kind}`, {
      method: 'POST', headers: { 'Content-Type': 'text/csv' }, body: csv
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      const errorMsg = data.error || `Server returned ${res.status}`;
      feedback.textContent = `Import failed: ${errorMsg}`;
      feedback.className = 'feedback error';
      return;
    }
    let summary = `Import complete: ${data.imported} imported, ${data.skipped} skipped, ${data.rejected} rejected.`;
    if (data.errors && data.errors.length > 0) {
      const errLines = data.errors.map(e => `Line ${e.line}: ${e.reason}`).join('\n');
      summary += `\nRejected rows:\n${errLines}`;
      feedback.className = 'feedback warning';
    } else {
      feedback.className = 'feedback success';
    }
    feedback.textContent = summary;
    await refresh();
  } catch (error) {
    feedback.textContent = `Import failed: ${error.message}`;
    feedback.className = 'feedback error';
  } finally {
    button.disabled = false;
  }
}

document.querySelector('#status').addEventListener('change', () => refresh().catch(e => { document.querySelector('#page-error').textContent = e.message; }));
document.querySelector('#customer')?.addEventListener('change', () => refresh().catch(e => { document.querySelector('#page-error').textContent = e.message; }));
document.querySelector('#sort-by')?.addEventListener('change', () => refresh().catch(e => { document.querySelector('#page-error').textContent = e.message; }));
document.querySelectorAll('form[data-kind]').forEach(form => form.addEventListener('submit', e => { e.preventDefault(); submitImport(form); }));
refresh().catch(e => { document.querySelector('#page-error').textContent = e.message; });
