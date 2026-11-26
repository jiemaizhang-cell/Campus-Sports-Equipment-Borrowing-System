const stateEl = document.getElementById('borrowing-state');
let initialState = {card_id: null, active_loan: null, active_reservation: null};
if (stateEl) {
  try {
    initialState = JSON.parse(stateEl.textContent || '{}');
  } catch (err) {
    // Keep defaults
  }
}

const feedback = document.getElementById('feedback');
const inventorySurface = document.getElementById('inventory-surface');
const inventoryHint = document.getElementById('inventory-hint');
const equipmentSearch = document.getElementById('equipment-search');
const availableOnlyBtn = document.getElementById('available-only-btn');
const equipmentPagination = document.getElementById('equipment-pagination');

const actionForms = document.getElementById('action-forms');
const borrowForm = document.getElementById('borrow-form');
const itemSelect = document.getElementById('equipment-item');
const selectionSummary = document.getElementById('selection-summary');
const borrowButton = document.getElementById('borrow-button');

const reserveForm = document.getElementById('reserve-form');
const reserveDuration = document.getElementById('reserve-duration');
const reserveButton = document.getElementById('reserve-button');
const durationButtons = document.querySelectorAll('.duration-btn');

const activeLoanNotice = document.getElementById('active-loan-notice');
const activeLoanItem = document.getElementById('active-loan-item');

const reservationCard = document.getElementById('reservation-card');
const resItemName = document.getElementById('res-item-name');
const resPickupCode = document.getElementById('res-pickup-code');
const resExpiresAt = document.getElementById('res-expires-at');
const resCountdown = document.getElementById('res-countdown');
const copyCodeButton = document.getElementById('copy-code-button');
const resCancelButton = document.getElementById('res-cancel-button');

const signedInCardId = initialState.card_id || null;
let currentLoan = initialState.active_loan || null;
let currentReservation = initialState.active_reservation || null;
let countdownTimer = null;
let cancelConfirmTimer = null;
let copyResetTimer = null;

function stopCountdown() {
  if (countdownTimer) {
    clearInterval(countdownTimer);
    countdownTimer = null;
  }
}

function resetCancelConfirm() {
  if (cancelConfirmTimer) {
    clearTimeout(cancelConfirmTimer);
    cancelConfirmTimer = null;
  }
  if (!resCancelButton) return;
  resCancelButton.dataset.armed = 'false';
  resCancelButton.classList.remove('btn-armed');
  resCancelButton.textContent = 'Cancel Reservation';
}

function formatCountdown(expiresAtUtc) {
  const targetMs = Date.parse(expiresAtUtc.replace(' ', 'T') + 'Z');
  if (Number.isNaN(targetMs)) return null;
  const remainingSec = Math.floor((targetMs - Date.now()) / 1000);
  if (remainingSec <= 0) return {expired: true, text: 'Expired'};
  const mins = Math.floor(remainingSec / 60);
  const secs = remainingSec % 60;
  return {
    expired: false,
    text: `${mins}m ${String(secs).padStart(2, '0')}s left`,
    localTime: new Date(targetMs).toLocaleTimeString([], {hour: '2-digit', minute: '2-digit', second: '2-digit'})
  };
}

function startCountdown(expiresAtUtc) {
  stopCountdown();
  const update = async () => {
    const state = formatCountdown(expiresAtUtc);
    if (!state) {
      resCountdown.hidden = true;
      return;
    }
    resCountdown.textContent = state.text;
    resCountdown.hidden = false;
    resCountdown.classList.toggle('is-expired', state.expired);
    if (state.localTime) {
      resExpiresAt.title = `Local time: ${state.localTime}`;
    }
    if (state.expired) {
      stopCountdown();
      await refreshEquipmentTable();
      applyWorkspaceState(null, null);
      showFeedback('Your reservation hold expired and the item was returned to stock. You may reserve or borrow again.', false);
    }
  };
  update();
  countdownTimer = setInterval(update, 1000);
}

function showFeedback(message, success) {
  if (!feedback) return;
  feedback.className = `feedback ${success ? 'success' : 'error'}`;
  feedback.textContent = message;
  feedback.hidden = false;
}

function updateInventoryState(readyForAction) {
  if (!inventorySurface || !inventoryHint) return;
  inventorySurface.classList.toggle('is-ready', Boolean(readyForAction));
  if (readyForAction) {
    inventoryHint.textContent = 'Click any available row to select it.';
  } else {
    inventoryHint.textContent = 'Return your active item at the sports desk counter or cancel your reservation first.';
  }
}

function updateSelectionSummary() {
  if (!itemSelect || !selectionSummary) return;
  const opt = itemSelect.options[itemSelect.selectedIndex];
  if (!itemSelect.value || !opt) {
    selectionSummary.hidden = true;
    selectionSummary.textContent = '';
    return;
  }
  const row = document.getElementById(`equipment-${itemSelect.value}`);
  const stock = row ? row.cells[1]?.textContent : '';
  selectionSummary.textContent = `Selected: ${opt.textContent}${stock ? ` (${stock} available)` : ''}`;
  selectionSummary.hidden = false;
}

function renderReservationCard(reservation) {
  currentReservation = reservation || null;
  resetCancelConfirm();
  if (!reservation) {
    stopCountdown();
    resCountdown.hidden = true;
    reservationCard.hidden = true;
    return;
  }
  resItemName.textContent = reservation.item_name;
  resPickupCode.textContent = reservation.pickup_code;
  resExpiresAt.textContent = reservation.expires_at;
  resExpiresAt.setAttribute('datetime', reservation.expires_at.replace(' ', 'T') + 'Z');
  copyCodeButton.textContent = 'Copy';
  reservationCard.hidden = false;
  startCountdown(reservation.expires_at);
}

function applyWorkspaceState(activeLoan = null, activeReservation = null) {
  currentLoan = activeLoan;
  renderReservationCard(activeReservation);

  activeLoanNotice.hidden = !activeLoan;
  if (activeLoan) {
    activeLoanItem.textContent = activeLoan.item_name;
  }

  const canBorrowOrReserve = Boolean(signedInCardId) && !activeLoan && !activeReservation && itemSelect && itemSelect.options.length > 1;
  actionForms.hidden = !canBorrowOrReserve;

  if (itemSelect) itemSelect.value = '';
  if (borrowButton) borrowButton.disabled = true;
  if (reserveButton) reserveButton.disabled = true;
  updateSelectionSummary();
  syncTableSelection('');
  updateInventoryState(canBorrowOrReserve);
}

function setSubmitting(submitting, activeButton = null) {
  const buttons = [borrowButton, reserveButton, resCancelButton];
  buttons.forEach((btn) => {
    if (btn) btn.removeAttribute('aria-busy');
  });
  if (submitting && activeButton) {
    activeButton.setAttribute('aria-busy', 'true');
  }

  if (itemSelect) itemSelect.disabled = submitting;
  if (borrowButton) borrowButton.disabled = submitting || !itemSelect?.value;
  if (reserveButton) reserveButton.disabled = submitting || !itemSelect?.value;
  if (resCancelButton) resCancelButton.disabled = submitting;
}

async function postJson(url, payload) {
  const response = await fetch(url, {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(payload)
  });
  if (response.status === 401) {
    window.location.href = '/login';
    return {response, data: {message: 'Session expired. Redirecting to sign in.'}};
  }
  let data = {};
  try {
    data = await response.json();
  } catch (err) {
    data = {message: `Server returned status ${response.status}.`};
  }
  return {response, data};
}

function updateStock(itemId, availableQuantity, flash = true) {
  const row = document.getElementById(`equipment-${itemId}`);
  const borrowOption = document.getElementById(`borrow-option-${itemId}`);
  const inStock = availableQuantity > 0;

  if (row) {
    row.cells[1].textContent = availableQuantity;
    row.cells[2].textContent = inStock ? 'Available' : 'Unavailable';
    row.cells[2].className = inStock ? 'stock-available' : 'stock-unavailable';
    row.dataset.selectable = inStock ? 'true' : 'false';
    if (flash) {
      row.classList.remove('stock-updated');
      void row.offsetWidth;
      row.classList.add('stock-updated');
    }
  }
  if (borrowOption) borrowOption.disabled = !inStock;
}

async function refreshEquipmentTable() {
  try {
    const response = await fetch('/api/equipment', {cache: 'no-store'});
    if (!response.ok) return;
    const data = await response.json();
    (data.equipment || []).forEach((item) => {
      updateStock(item.item_id, item.available_quantity, false);
    });
    applyEquipmentFiltersAndPage();
  } catch (err) {
    // Keep current values if refresh fails
  }
}

function syncTableSelection(selectedItemId) {
  document.querySelectorAll('.equipment-table tbody tr').forEach((row) => {
    const id = row.id.replace('equipment-', '');
    row.classList.toggle('is-selected', Boolean(selectedItemId) && id === String(selectedItemId));
  });
}

function initSelectableRows() {
  document.querySelectorAll('.equipment-table tbody tr').forEach((row) => {
    const qty = Number(row.cells[1]?.textContent || '0');
    row.dataset.selectable = qty > 0 ? 'true' : 'false';
    row.addEventListener('click', () => {
      if (row.dataset.selectable !== 'true') return;
      if (actionForms.hidden) return;
      const itemId = row.id.replace('equipment-', '');
      itemSelect.value = itemId;
      borrowButton.disabled = !itemSelect.value;
      reserveButton.disabled = !itemSelect.value;
      updateSelectionSummary();
      syncTableSelection(itemId);
      actionForms.scrollIntoView({behavior: 'smooth', block: 'nearest'});
    });
  });
}

durationButtons.forEach((btn) => {
  btn.addEventListener('click', () => {
    const duration = btn.dataset.duration || '10';
    reserveDuration.value = duration;
    durationButtons.forEach((b) => b.classList.toggle('is-active', b === btn));
  });
});

if (itemSelect) {
  itemSelect.addEventListener('change', () => {
    const hasSelection = Boolean(itemSelect.value);
    borrowButton.disabled = !hasSelection;
    reserveButton.disabled = !hasSelection;
    updateSelectionSummary();
    syncTableSelection(itemSelect.value);
  });
}

async function submitPickupCodeRequest(itemId, durationMinutes, triggerButton, fallbackError) {
  setSubmitting(true, triggerButton);
  try {
    const {response, data} = await postJson(reserveForm.action, {
      item_id: itemId,
      duration_minutes: durationMinutes
    });
    if (!response.ok) {
      showFeedback(data.message || fallbackError, false);
      if (response.status === 409) await refreshEquipmentTable();
      return;
    }

    const reservation = data.reservation;
    updateStock(itemId, reservation.available_quantity);
    applyWorkspaceState(null, reservation);
    showFeedback(data.message, true);
  } catch (error) {
    showFeedback('Could not confirm the pickup code. Please refresh and try again.', false);
  } finally {
    setSubmitting(false);
  }
}

if (borrowForm) {
  borrowForm.addEventListener('submit', async (event) => {
    event.preventDefault();
    if (!signedInCardId || currentLoan || currentReservation || !itemSelect.value) {
      return;
    }
    await submitPickupCodeRequest(itemSelect.value, 5, borrowButton, 'Unable to borrow this item.');
  });
}

if (reserveForm) {
  reserveForm.addEventListener('submit', async (event) => {
    event.preventDefault();
    if (!signedInCardId || currentLoan || currentReservation || !itemSelect.value) {
      return;
    }
    const durationMinutes = Number(reserveDuration.value || '10');
    await submitPickupCodeRequest(itemSelect.value, durationMinutes, reserveButton, 'Unable to reserve this item.');
  });
}

if (copyCodeButton) {
  copyCodeButton.addEventListener('click', async () => {
    const code = resPickupCode.textContent;
    if (!code) return;
    if (copyResetTimer) clearTimeout(copyResetTimer);
    try {
      await navigator.clipboard.writeText(code);
      copyCodeButton.textContent = 'Copied!';
      copyResetTimer = setTimeout(() => {
        copyCodeButton.textContent = 'Copy';
      }, 2000);
    } catch (err) {
      copyCodeButton.textContent = code;
    }
  });
}

if (resCancelButton) {
  resCancelButton.addEventListener('click', async () => {
    if (!signedInCardId || !currentReservation) return;
    if (resCancelButton.dataset.armed !== 'true') {
      resCancelButton.dataset.armed = 'true';
      resCancelButton.classList.add('btn-armed');
      resCancelButton.textContent = 'Confirm Cancel?';
      cancelConfirmTimer = setTimeout(resetCancelConfirm, 3500);
      return;
    }

    resetCancelConfirm();
    const {reservation_id: reservationId, item_id: itemId} = currentReservation;
    setSubmitting(true, resCancelButton);
    try {
      const {response, data} = await postJson('/api/reservations/cancel', {
        reservation_id: reservationId
      });
      if (!response.ok) {
        showFeedback(data.message || 'Unable to cancel this reservation.', false);
        if (response.status === 409) {
          applyWorkspaceState(null, null);
          await refreshEquipmentTable();
        }
        return;
      }
      updateStock(itemId, data.reservation.available_quantity);
      applyWorkspaceState(null, null);
      showFeedback(data.message, true);
    } catch (err) {
      showFeedback('Connection error while cancelling reservation.', false);
    } finally {
      setSubmitting(false);
    }
  });
}

let showAvailableOnly = false;
let currentEquipPage = 1;
const EQUIP_PAGE_SIZE = 5;

function applyEquipmentFiltersAndPage() {
  const rows = Array.from(document.querySelectorAll('.equipment-table tbody tr'));
  const query = (equipmentSearch?.value || '').trim().toLowerCase();
  const matched = rows.filter((row) => {
    const name = (row.cells[0]?.textContent || '').toLowerCase();
    const qty = Number(row.cells[1]?.textContent || '0');
    const matchQuery = !query || name.includes(query);
    const matchAvail = !showAvailableOnly || qty > 0;
    return matchQuery && matchAvail;
  });

  const totalPages = Math.max(1, Math.ceil(matched.length / EQUIP_PAGE_SIZE));
  if (currentEquipPage > totalPages) currentEquipPage = totalPages;
  const start = (currentEquipPage - 1) * EQUIP_PAGE_SIZE;
  const pageSet = new Set(matched.slice(start, start + EQUIP_PAGE_SIZE));

  rows.forEach((row) => {
    row.hidden = !pageSet.has(row);
  });

  if (!equipmentPagination) return;
  if (matched.length <= EQUIP_PAGE_SIZE) {
    equipmentPagination.hidden = true;
    equipmentPagination.innerHTML = '';
    return;
  }

  equipmentPagination.hidden = false;
  const from = start + 1;
  const to = Math.min(start + EQUIP_PAGE_SIZE, matched.length);
  equipmentPagination.innerHTML = `
    <span class="page-info">Showing ${from}–${to} of ${matched.length}</span>
    <div class="page-controls">
      <button type="button" class="page-btn" data-page="prev" ${currentEquipPage <= 1 ? 'disabled' : ''}>Prev</button>
      <span class="page-num">${currentEquipPage} / ${totalPages}</span>
      <button type="button" class="page-btn" data-page="next" ${currentEquipPage >= totalPages ? 'disabled' : ''}>Next</button>
    </div>
  `;
  equipmentPagination.querySelector('[data-page="prev"]')?.addEventListener('click', () => {
    if (currentEquipPage > 1) {
      currentEquipPage -= 1;
      applyEquipmentFiltersAndPage();
    }
  });
  equipmentPagination.querySelector('[data-page="next"]')?.addEventListener('click', () => {
    if (currentEquipPage < totalPages) {
      currentEquipPage += 1;
      applyEquipmentFiltersAndPage();
    }
  });
}

if (equipmentSearch) {
  equipmentSearch.addEventListener('input', () => {
    currentEquipPage = 1;
    applyEquipmentFiltersAndPage();
  });
}

if (availableOnlyBtn) {
  availableOnlyBtn.addEventListener('click', () => {
    showAvailableOnly = !showAvailableOnly;
    availableOnlyBtn.classList.toggle('is-active', showAvailableOnly);
    availableOnlyBtn.setAttribute('aria-pressed', String(showAvailableOnly));
    currentEquipPage = 1;
    applyEquipmentFiltersAndPage();
  });
}

initSelectableRows();
applyEquipmentFiltersAndPage();
applyWorkspaceState(currentLoan, currentReservation);

const changePasswordBtn = document.getElementById('change-password-btn');
const passwordModal = document.getElementById('password-modal');
const passwordForm = document.getElementById('password-form');
const passwordFeedback = document.getElementById('password-feedback');
const currentPasswordInput = document.getElementById('current-password');
const newPasswordInput = document.getElementById('new-password');
const confirmPasswordInput = document.getElementById('confirm-password');
const passwordSubmitBtn = document.getElementById('password-submit-btn');
const passwordCancelBtn = document.getElementById('password-cancel-btn');
const passwordCloseBtn = document.getElementById('password-modal-close');

function showPasswordError(message) {
  if (!passwordFeedback) return;
  passwordFeedback.className = 'feedback modal-feedback error';
  passwordFeedback.textContent = message;
  passwordFeedback.hidden = false;
}

function clearPasswordFeedback() {
  if (!passwordFeedback) return;
  passwordFeedback.hidden = true;
  passwordFeedback.textContent = '';
}

function closePasswordModal() {
  if (passwordForm) passwordForm.reset();
  [currentPasswordInput, newPasswordInput, confirmPasswordInput].forEach((el) => {
    el?.removeAttribute('aria-invalid');
  });
  clearPasswordFeedback();
  if (passwordModal?.open) passwordModal.close();
}

if (changePasswordBtn && passwordModal) {
  changePasswordBtn.addEventListener('click', () => {
    clearPasswordFeedback();
    passwordModal.showModal();
    currentPasswordInput?.focus();
  });
  passwordCloseBtn?.addEventListener('click', closePasswordModal);
  passwordCancelBtn?.addEventListener('click', closePasswordModal);
  passwordModal.addEventListener('click', (event) => {
    if (event.target === passwordModal) closePasswordModal();
  });
  passwordModal.addEventListener('close', () => {
    if (passwordForm) passwordForm.reset();
    clearPasswordFeedback();
  });
}

[currentPasswordInput, newPasswordInput, confirmPasswordInput].forEach((el) => {
  el?.addEventListener('input', () => {
    el.removeAttribute('aria-invalid');
    clearPasswordFeedback();
  });
});

if (passwordForm) {
  passwordForm.addEventListener('submit', async (event) => {
    event.preventDefault();
    clearPasswordFeedback();

    const currentPassword = currentPasswordInput.value;
    const newPassword = newPasswordInput.value;
    const confirmPassword = confirmPasswordInput.value;

    if (!currentPassword) {
      currentPasswordInput.setAttribute('aria-invalid', 'true');
      showPasswordError('Current password is required.');
      return;
    }
    if (newPassword.length < 6 || newPassword.length > 64 || !newPassword.trim()) {
      newPasswordInput.setAttribute('aria-invalid', 'true');
      showPasswordError('New password must be 6–64 characters and cannot be blank spaces.');
      return;
    }
    if (newPassword !== confirmPassword) {
      confirmPasswordInput.setAttribute('aria-invalid', 'true');
      showPasswordError('New passwords do not match.');
      return;
    }
    if (newPassword === currentPassword) {
      newPasswordInput.setAttribute('aria-invalid', 'true');
      showPasswordError('New password must be different from your current password.');
      return;
    }

    passwordSubmitBtn.disabled = true;
    passwordSubmitBtn.setAttribute('aria-busy', 'true');
    try {
      const {response, data} = await postJson(passwordForm.action, {
        current_password: currentPassword,
        new_password: newPassword,
        confirm_password: confirmPassword
      });
      if (!response.ok) {
        if (response.status === 401) {
          currentPasswordInput.setAttribute('aria-invalid', 'true');
        }
        showPasswordError(data.message || 'Unable to update password.');
        return;
      }
      closePasswordModal();
      showFeedback(data.message || 'Password updated successfully.', true);
    } catch (err) {
      showPasswordError('Connection error while updating password.');
    } finally {
      passwordSubmitBtn.disabled = false;
      passwordSubmitBtn.removeAttribute('aria-busy');
    }
  });
}
