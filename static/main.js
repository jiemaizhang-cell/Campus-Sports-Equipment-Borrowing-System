const form = document.getElementById('card-form');
const input = document.getElementById('card-id');
const feedback = document.getElementById('feedback');
const cardMessage = document.getElementById('card-message');
const loanStatus = document.getElementById('loan-status');
const verifyButton = document.getElementById('submit-button');
const borrowForm = document.getElementById('borrow-form');
const itemSelect = document.getElementById('equipment-item');
const borrowButton = document.getElementById('borrow-button');
const returnForm = document.getElementById('return-form');
const returnButton = document.getElementById('return-button');
let verifiedCardId = null;
let currentLoan = null;

function setVerifiedCard(cardId, activeLoan = null) {
  verifiedCardId = cardId;
  currentLoan = activeLoan;
  returnForm.hidden = !activeLoan;
  borrowForm.hidden = !cardId || !!activeLoan || itemSelect.options.length <= 1;
  itemSelect.value = '';
  borrowButton.disabled = true;
}

function clearVerification() {
  setVerifiedCard(null);
  feedback.hidden = true;
}

function setSubmitting(submitting) {
  verifyButton.disabled = submitting;
  input.readOnly = submitting;
  itemSelect.disabled = submitting;
  borrowButton.disabled = submitting || !itemSelect.value;
  returnButton.disabled = submitting;
}

function showFeedback(message, success, activeLoan = null) {
  feedback.className = `feedback ${success ? 'success' : 'error'}`;
  cardMessage.textContent = message;
  loanStatus.hidden = !success;
  if (success) {
    loanStatus.textContent = activeLoan
      ? `Active loan: ${activeLoan.item_name}.`
      : 'No equipment is currently borrowed.';
  }
  feedback.hidden = false;
}

async function postForm(formToSubmit, payload) {
  const response = await fetch(formToSubmit.action, {
    method: formToSubmit.method,
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(payload)
  });
  return {response, data: await response.json()};
}

function updateStock(itemId, availableQuantity) {
  const row = document.getElementById(`equipment-${itemId}`);
  const option = document.getElementById(`borrow-option-${itemId}`);
  const inStock = availableQuantity > 0;
  if (row) {
    row.cells[1].textContent = availableQuantity;
    row.cells[2].textContent = inStock ? 'Available' : 'Unavailable';
    row.cells[2].className = inStock ? 'stock-available' : 'stock-unavailable';
  }
  if (option) {
    option.disabled = !inStock;
  }
}

input.addEventListener('input', clearVerification);
itemSelect.addEventListener('change', () => {
  borrowButton.disabled = !itemSelect.value;
});

form.addEventListener('submit', async (event) => {
  event.preventDefault();
  clearVerification();
  setSubmitting(true);
  try {
    const {response, data} = await postForm(form, {card_id: input.value});
    const verified = response.ok && data.valid;
    showFeedback(data.message || 'Unable to validate the card ID.', verified, data.active_loan);
    if (verified) {
      setVerifiedCard(data.card_id, data.active_loan);
    }
  } catch (error) {
    showFeedback('Connection error. Please check that the Flask server is running.', false);
  } finally {
    setSubmitting(false);
  }
});

borrowForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  if (!verifiedCardId || currentLoan || !itemSelect.value) {
    return;
  }

  const itemId = itemSelect.value;
  setSubmitting(true);
  try {
    const {response, data} = await postForm(borrowForm, {
      card_id: verifiedCardId,
      item_id: itemId
    });
    if (!response.ok) {
      showFeedback(data.message || 'Unable to borrow this item.', false);
      return;
    }

    updateStock(itemId, data.loan.available_quantity);
    setVerifiedCard(verifiedCardId, data.active_loan);
    showFeedback(data.message, true, data.active_loan);
  } catch (error) {
    clearVerification();
    showFeedback('Could not confirm the loan. Verify the card again to check its status.', false);
  } finally {
    setSubmitting(false);
  }
});

returnForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  if (!verifiedCardId || !currentLoan) {
    return;
  }

  const {loan_id: loanId, item_id: itemId} = currentLoan;
  setSubmitting(true);
  try {
    const {response, data} = await postForm(returnForm, {
      card_id: verifiedCardId,
      loan_id: loanId
    });
    if (!response.ok) {
      if (response.status === 409) {
        clearVerification();
      }
      showFeedback(data.message || 'Unable to return this item.', false);
      return;
    }

    updateStock(itemId, data.loan.available_quantity);
    setVerifiedCard(verifiedCardId);
    showFeedback(data.message, true);
  } catch (error) {
    clearVerification();
    showFeedback('Could not confirm the return. Verify the card again to check its status.', false);
  } finally {
    setSubmitting(false);
  }
});
