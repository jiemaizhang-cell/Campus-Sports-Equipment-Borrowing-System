const counterForm = document.getElementById('counter-claim-form');
const counterInput = document.getElementById('counter-pickup-code');
const counterSubmit = document.getElementById('counter-claim-submit');
const counterFeedback = document.getElementById('counter-feedback');

const FLASH_KEY = 'sportsDeskFlash';
let toastTimer = null;

function showCounterFeedback(message, success) {
  if (!counterFeedback) return;
  if (toastTimer) clearTimeout(toastTimer);
  counterFeedback.className = `feedback toast-banner ${success ? 'success' : 'error'}`;
  counterFeedback.innerHTML = '';

  const text = document.createElement('span');
  text.textContent = message;
  const closeBtn = document.createElement('button');
  closeBtn.type = 'button';
  closeBtn.className = 'toast-close';
  closeBtn.setAttribute('aria-label', 'Dismiss notification');
  closeBtn.textContent = '×';
  closeBtn.addEventListener('click', () => {
    counterFeedback.hidden = true;
  });

  counterFeedback.appendChild(text);
  counterFeedback.appendChild(closeBtn);
  counterFeedback.hidden = false;

  toastTimer = setTimeout(() => {
    counterFeedback.hidden = true;
  }, success ? 4000 : 5500);
}

function consumeFlashBanner() {
  try {
    const raw = sessionStorage.getItem(FLASH_KEY);
    if (!raw) return;
    sessionStorage.removeItem(FLASH_KEY);
    const flash = JSON.parse(raw);
    if (flash && flash.message) {
      showCounterFeedback(flash.message, Boolean(flash.success));
    }
  } catch (err) {
    // Ignore storage issues
  }
}

function saveFlashAndReload(message) {
  try {
    sessionStorage.setItem(FLASH_KEY, JSON.stringify({message, success: true}));
  } catch (err) {
    // Ignore storage issues
  }
  window.location.reload();
}

async function postCounterAction(url, payload) {
  const response = await fetch(url, {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(payload)
  });
  let data = {};
  try {
    data = await response.json();
  } catch (err) {
    data = {message: `Server returned status ${response.status}.`};
  }
  return {response, data};
}

if (counterInput) {
  counterInput.addEventListener('input', () => {
    counterInput.removeAttribute('aria-invalid');
    const cleaned = counterInput.value.replace(/\s+/g, '').toUpperCase();
    if (counterInput.value !== cleaned) {
      counterInput.value = cleaned;
    }
  });
}

if (counterForm) {
  counterForm.addEventListener('submit', async (event) => {
    event.preventDefault();
    counterFeedback.hidden = true;
    counterSubmit.disabled = true;
    counterSubmit.setAttribute('aria-busy', 'true');
    try {
      const {response, data} = await postCounterAction(counterForm.action, {
        pickup_code: counterInput.value
      });
      if (!response.ok) {
        counterInput.setAttribute('aria-invalid', 'true');
        showCounterFeedback(data.message || 'Unable to hand out this reservation.', false);
        return;
      }
      counterInput.removeAttribute('aria-invalid');
      saveFlashAndReload(data.message || 'Equipment handed out.');
    } catch (err) {
      showCounterFeedback('Connection error. Please check that the Flask server is running.', false);
    } finally {
      counterSubmit.disabled = false;
      counterSubmit.removeAttribute('aria-busy');
    }
  });
}

consumeFlashBanner();
