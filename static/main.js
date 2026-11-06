const form = document.getElementById('card-form');
const input = document.getElementById('card-id');
const feedback = document.getElementById('feedback');
const button = document.getElementById('submit-button');

form.addEventListener('submit', async (event) => {
  event.preventDefault();
  button.disabled = true;
  feedback.hidden = true;
  try {
    const response = await fetch('/api/validate-card', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({card_id: input.value})
    });
    const data = await response.json();
    feedback.className = `feedback ${response.ok && data.valid ? 'success' : 'error'}`;
    feedback.textContent = data.message || 'Unable to validate the card ID.';
    feedback.hidden = false;
  } catch (error) {
    feedback.className = 'feedback error';
    feedback.textContent = 'Connection error. Please check that the Flask server is running.';
    feedback.hidden = false;
  } finally {
    button.disabled = false;
  }
});
