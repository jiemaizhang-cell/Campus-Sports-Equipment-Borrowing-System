const loginForm = document.getElementById('login-form');
const loginCardInput = document.getElementById('login-card-id');
const loginPasswordInput = document.getElementById('login-password');
const loginSubmitBtn = document.getElementById('login-submit');
const loginFeedback = document.getElementById('login-feedback');

function showLoginError(message) {
  if (!loginFeedback) return;
  loginFeedback.className = 'feedback error';
  loginFeedback.textContent = message;
  loginFeedback.hidden = false;
}

function clearLoginError() {
  if (!loginFeedback) return;
  loginFeedback.hidden = true;
  loginFeedback.textContent = '';
}

if (loginCardInput) {
  loginCardInput.addEventListener('input', () => {
    loginCardInput.removeAttribute('aria-invalid');
    clearLoginError();
  });
}

if (loginPasswordInput) {
  loginPasswordInput.addEventListener('input', () => {
    loginPasswordInput.removeAttribute('aria-invalid');
    clearLoginError();
  });
}

if (loginForm) {
  loginForm.addEventListener('submit', async (event) => {
    event.preventDefault();
    clearLoginError();
    loginSubmitBtn.disabled = true;
    loginSubmitBtn.setAttribute('aria-busy', 'true');

    try {
      const response = await fetch(loginForm.action, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
          card_id: loginCardInput.value,
          password: loginPasswordInput.value
        })
      });
      let data = {};
      try {
        data = await response.json();
      } catch (err) {
        data = {message: `Server returned status ${response.status}.`};
      }

      if (!response.ok || !data.valid) {
        if (response.status === 400 && /card/i.test(data.message || '')) {
          loginCardInput.setAttribute('aria-invalid', 'true');
        } else if (response.status === 400 && /password/i.test(data.message || '')) {
          loginPasswordInput.setAttribute('aria-invalid', 'true');
        } else {
          loginCardInput.setAttribute('aria-invalid', 'true');
          loginPasswordInput.setAttribute('aria-invalid', 'true');
        }
        showLoginError(data.message || 'Invalid student card ID or password.');
        return;
      }

      window.location.href = '/';
    } catch (err) {
      showLoginError('Connection error. Please check that the Flask server is running.');
    } finally {
      loginSubmitBtn.disabled = false;
      loginSubmitBtn.removeAttribute('aria-busy');
    }
  });
}
