const ticket = document.getElementById('ticket');
const button = document.getElementById('analyzeBtn');
const status = document.getElementById('status');
const results = document.getElementById('results');

const pct = (n) => `${Math.round(Number(n) * 100)}%`;

document.querySelectorAll('.example').forEach((el) => {
  el.addEventListener('click', () => { ticket.value = el.dataset.ticket; });
});

button.addEventListener('click', async () => {
  const value = ticket.value.trim();
  if (value.length < 5) return;

  button.disabled = true;
  status.textContent = 'Running one Jev request with multiple typed questions...';
  results.classList.add('hidden');

  try {
    const response = await fetch('/api/analyze', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ticket: value }),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || 'Request failed');

    document.getElementById('department').textContent = data.jev.department;
    document.getElementById('departmentConfidence').textContent = `${pct(data.jev.department_confidence)} confidence`;
    document.getElementById('urgency').textContent = Number(data.jev.urgency_score).toFixed(2);
    document.getElementById('refund').textContent = pct(data.jev.refund_probability);
    document.getElementById('humanProb').textContent = pct(data.jev.human_review_probability);
    document.getElementById('route').textContent = data.automation.route;
    document.getElementById('routeReason').textContent = data.automation.reason;
    document.getElementById('reply').textContent = data.suggested_reply;

    status.textContent = '';
    results.classList.remove('hidden');
  } catch (err) {
    status.textContent = err.message;
  } finally {
    button.disabled = false;
  }
});
