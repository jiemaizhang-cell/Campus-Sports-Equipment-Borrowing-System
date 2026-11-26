const form = document.getElementById('card-form');
const input = document.getElementById('card-id');
const verifyZone = document.getElementById('verify-zone');
const verifiedStrip = document.getElementById('verified-strip');
const verifiedCardDisplay = document.getElementById('verified-card-display');
const reopenModalBtn = document.getElementById('reopen-modal-btn');
const switchCardBtn = document.getElementById('switch-card-btn');

const actionModal = document.getElementById('action-modal');
const modalCardId = document.getElementById('modal-card-id');
const modalSubtitle = document.getElementById('modal-subtitle');
const modalCloseBtn = document.getElementById('modal-close-btn');
const modalDoneBtn = document.getElementById('modal-done-btn');
const modalSwitchBtn = document.getElementById('modal-switch-btn');
const modalFeedback = document.getElementById('modal-feedback');

const feedback = document.getElementById('feedback');
const cardMessage = document.getElementById('card-message');
const loanStatus = document.getElementById('loan-status');
const verifyButton = document.getElementById('submit-button');

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

const demoLinks = document.querySelectorAll('.demo-link');
let verifiedCardId = null;
let currentLoan = null;
let currentReservation = null;
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
      setVerifiedCard(verifiedCardId, null, null);
      showFeedback('Your reservation hold expired and the item was returned to stock. You may reserve or borrow again.', false);
    }
  };
  update();
  countdownTimer = setInterval(update, 1000);
}

function updateInventoryState(verified, readyForAction) {
  inventorySurface.classList.toggle('is-ready', Boolean(readyForAction));
  if (!verified) {
    inventoryHint.textContent = 'Verify a card to borrow or reserve.';
  } else if (readyForAction) {
    inventoryHint.textContent = 'Click any available row to select it.';
  } else {
    inventoryHint.textContent = 'Return your active item at the Pickup Counter or cancel your reservation first.';
  }
}

function updateSelectionSummary() {
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

function openActionModal() {
  if (actionModal && !actionModal.open) {
    actionModal.showModal();
  }
}

function closeActionModal() {
  if (actionModal && actionModal.open) {
    actionModal.close();
  }
}

function showModalFeedback(message, success) {
  if (!modalFeedback) return;
  modalFeedback.className = `feedback modal-feedback ${success ? 'success' : 'error'}`;
  modalFeedback.textContent = message;
  modalFeedback.hidden = false;
}

function clearModalFeedback() {
  if (!modalFeedback) return;
  modalFeedback.hidden = true;
  modalFeedback.textContent = '';
}

function setVerifiedCard(cardId, activeLoan = null, activeReservation = null) {
  verifiedCardId = cardId;
  currentLoan = activeLoan;
  renderReservationCard(activeReservation);

  const isVerified = Boolean(cardId);
  verifyZone.hidden = isVerified;
  verifiedStrip.hidden = !isVerified;
  if (isVerified) {
    verifiedCardDisplay.textContent = cardId;
    if (modalCardId) modalCardId.textContent = cardId;
    if (modalSubtitle) {
      if (activeLoan) {
        modalSubtitle.textContent = 'This card currently has an item checked out.';
      } else if (activeReservation) {
        modalSubtitle.textContent = 'Show this pickup code at the Pickup Counter.';
      } else {
        modalSubtitle.textContent = 'Choose equipment to borrow now or reserve for pickup.';
      }
    }
    input.removeAttribute('aria-invalid');
  } else {
    closeActionModal();
    clearModalFeedback();
  }

  activeLoanNotice.hidden = !activeLoan;
  if (activeLoan) {
    activeLoanItem.textContent = activeLoan.item_name;
  }

  const canBorrowOrReserve = isVerified && !activeLoan && !activeReservation && itemSelect.options.length > 1;
  actionForms.hidden = !canBorrowOrReserve;
  borrowForm.hidden = !canBorrowOrReserve;
  reserveForm.hidden = !canBorrowOrReserve;

  itemSelect.value = '';
  borrowButton.disabled = true;
  reserveButton.disabled = true;
  updateSelectionSummary();
  syncTableSelection('');
  updateInventoryState(isVerified, canBorrowOrReserve);
}

function clearVerification() {
  setVerifiedCard(null);
  feedback.hidden = true;
}

function setSubmitting(submitting, activeButton = null) {
  const buttons = [verifyButton, borrowButton, reserveButton, resCancelButton];
  buttons.forEach((btn) => {
    if (btn) btn.removeAttribute('aria-busy');
  });
  if (submitting && activeButton) {
    activeButton.setAttribute('aria-busy', 'true');
  }

  verifyButton.disabled = submitting;
  input.readOnly = submitting;
  itemSelect.disabled = submitting;
  borrowButton.disabled = submitting || !itemSelect.value;
  reserveButton.disabled = submitting || !itemSelect.value;
  resCancelButton.disabled = submitting;
}

function showFeedback(message, success, activeLoan = null, activeReservation = null) {
  feedback.className = `feedback ${success ? 'success' : 'error'}`;
  cardMessage.textContent = message;
  loanStatus.hidden = !success;
  if (success) {
    if (activeLoan) {
      loanStatus.textContent = `Active loan: ${activeLoan.item_name} (return at Pickup Counter).`;
    } else if (activeReservation) {
      loanStatus.textContent = `Show pickup code ${activeReservation.pickup_code} at the Pickup Counter before the hold expires.`;
    } else {
      loanStatus.textContent = 'Eligible to borrow or reserve 1 item.';
    }
  }
  feedback.hidden = false;
}

async function postForm(url, method, payload) {
  const response = await fetch(url, {
    method: method || 'POST',
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
      clearModalFeedback();
      openActionModal();
    });
  });
}

async function verifyCardSubmit() {
  clearVerification();
  clearModalFeedback();
  setSubmitting(true, verifyButton);
  try {
    const {response, data} = await postForm(form.action, form.method, {card_id: input.value});
    const verified = response.ok && data.valid;
    if (!verified) {
      input.setAttribute('aria-invalid', 'true');
      showFeedback(data.message || 'Unable to validate the card ID.', false);
      return;
    }

    let activeReservation = null;
    if (!data.active_loan) {
      const resCheck = await postForm('/api/reservations/status', 'POST', {card_id: data.card_id});
      if (resCheck.response.ok) {
        activeReservation = resCheck.data.active_reservation || null;
      }
      await refreshEquipmentTable();
    }

    setVerifiedCard(data.card_id, data.active_loan, activeReservation);
    showFeedback(data.message, true, data.active_loan, activeReservation);
    openActionModal();
  } catch (error) {
    showFeedback('Connection error. Please check that the Flask server is running.', false);
  } finally {
    setSubmitting(false);
  }
}

if (reopenModalBtn) {
  reopenModalBtn.addEventListener('click', () => {
    clearModalFeedback();
    openActionModal();
  });
}

if (modalCloseBtn) modalCloseBtn.addEventListener('click', closeActionModal);
if (modalDoneBtn) modalDoneBtn.addEventListener('click', closeActionModal);

if (modalSwitchBtn) {
  modalSwitchBtn.addEventListener('click', () => {
    clearVerification();
    input.focus();
    input.select();
  });
}

if (actionModal) {
  actionModal.addEventListener('click', (event) => {
    if (event.target === actionModal) {
      closeActionModal();
    }
  });
  actionModal.addEventListener('close', () => {
    if (verifiedCardId !== null) {
      setVerifiedCard(null);
      feedback.hidden = true;
      input.focus();
    }
  });
}

switchCardBtn.addEventListener('click', () => {
  clearVerification();
  input.focus();
  input.select();
});

document.addEventListener('keydown', (event) => {
  if (event.key === 'Escape' && verifiedCardId) {
    clearVerification();
    input.focus();
    input.select();
  }
});

demoLinks.forEach((link) => {
  link.addEventListener('click', () => {
    input.value = link.dataset.cardId || '';
    input.removeAttribute('aria-invalid');
    verifyCardSubmit();
  });
});

durationButtons.forEach((btn) => {
  btn.addEventListener('click', () => {
    const duration = btn.dataset.duration || '10';
    reserveDuration.value = duration;
    durationButtons.forEach((b) => b.classList.toggle('is-active', b === btn));
  });
});

input.addEventListener('input', () => {
  input.removeAttribute('aria-invalid');
  clearVerification();
});

itemSelect.addEventListener('change', () => {
  const hasSelection = Boolean(itemSelect.value);
  borrowButton.disabled = !hasSelection;
  reserveButton.disabled = !hasSelection;
  updateSelectionSummary();
  syncTableSelection(itemSelect.value);
});

form.addEventListener('submit', (event) => {
  event.preventDefault();
  verifyCardSubmit();
});

async function submitPickupCodeRequest(itemId, durationMinutes, triggerButton, fallbackError) {
  setSubmitting(true, triggerButton);
  try {
    const {response, data} = await postForm(reserveForm.action, reserveForm.method, {
      card_id: verifiedCardId,
      item_id: itemId,
      duration_minutes: durationMinutes
    });
    if (!response.ok) {
      showModalFeedback(data.message || fallbackError, false);
      if (response.status === 409) await refreshEquipmentTable();
      return;
    }

    const reservation = data.reservation;
    updateStock(itemId, reservation.available_quantity);
    setVerifiedCard(verifiedCardId, null, reservation);
    showFeedback(data.message, true, null, reservation);
    showModalFeedback(data.message, true);
  } catch (error) {
    clearVerification();
    showFeedback('Could not confirm the pickup code. Verify the card again to check its status.', false);
  } finally {
    setSubmitting(false);
  }
}

borrowForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  if (!verifiedCardId || currentLoan || currentReservation || !itemSelect.value) {
    return;
  }

  await submitPickupCodeRequest(itemSelect.value, 5, borrowButton, 'Unable to borrow this item.');
});

reserveForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  if (!verifiedCardId || currentLoan || currentReservation || !itemSelect.value) {
    return;
  }

  const durationMinutes = Number(reserveDuration.value || '10');
  await submitPickupCodeRequest(itemSelect.value, durationMinutes, reserveButton, 'Unable to reserve this item.');
});

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

resCancelButton.addEventListener('click', async () => {
  if (!verifiedCardId || !currentReservation) return;
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
    const {response, data} = await postForm('/api/reservations/cancel', 'POST', {
      card_id: verifiedCardId,
      reservation_id: reservationId
    });
    if (!response.ok) {
      showModalFeedback(data.message || 'Unable to cancel this reservation.', false);
      if (response.status === 409) {
        setVerifiedCard(verifiedCardId, null, null);
        await refreshEquipmentTable();
      }
      return;
    }
    updateStock(itemId, data.reservation.available_quantity);
    setVerifiedCard(verifiedCardId, null, null);
    showFeedback(data.message, true, null, null);
    showModalFeedback(data.message, true);
  } catch (err) {
    showModalFeedback('Connection error while cancelling reservation.', false);
  } finally {
    setSubmitting(false);
  }
});

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
  if (matched.length === 0) {
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
