const form = document.getElementById('card-form');
const input = document.getElementById('card-id');
const feedback = document.getElementById('feedback');
const cardMessage = document.getElementById('card-message');
const loanStatus = document.getElementById('loan-status');
const button = document.getElementById('submit-button');

input.addEventListener('input', () => {
  feedback.hidden = true;
});

form.addEventListener('submit', async (event) => {
  event.preventDefault();
  button.disabled = true;
  input.readOnly = true;
  feedback.hidden = true;
  loanStatus.hidden = true;
  try {
    const response = await fetch(form.action, {
      method: form.method,
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({card_id: input.value})
    });
    const data = await response.json();
    const verified = response.ok && data.valid;
    feedback.className = `feedback ${verified ? 'success' : 'error'}`;
    cardMessage.textContent = data.message || 'Unable to validate the card ID.';
    if (verified) {
      loanStatus.textContent = data.active_loan
        ? `Active loan: ${data.active_loan.item_name}.`
        : 'No equipment is currently borrowed.';
      loanStatus.hidden = false;
    }
    feedback.hidden = false;
  } catch (error) {
    feedback.className = 'feedback error';
    cardMessage.textContent = 'Connection error. Please check that the Flask server is running.';
    feedback.hidden = false;
  } finally {
    input.readOnly = false;
    button.disabled = false;
  }
});
