const staffClaimForm = document.getElementById('staff-claim-form');
const staffPickupInput = document.getElementById('staff-pickup-code');
const staffFeedback = document.getElementById('staff-action-feedback');
const loanSearchInput = document.getElementById('loan-search');

const FLASH_KEY = 'sportsDeskFlash';
let currentResFilter = 'all';
let currentLoanFilter = 'all';
let staffToastTimer = null;

function showStaffFeedback(message, success) {
  if (!staffFeedback) return;
  if (staffToastTimer) clearTimeout(staffToastTimer);
  staffFeedback.className = `feedback toast-banner ${success ? 'success' : 'error'}`;
  staffFeedback.innerHTML = '';

  const text = document.createElement('span');
  text.textContent = message;
  const closeBtn = document.createElement('button');
  closeBtn.type = 'button';
  closeBtn.className = 'toast-close';
  closeBtn.setAttribute('aria-label', 'Dismiss notification');
  closeBtn.textContent = '×';
  closeBtn.addEventListener('click', () => {
    staffFeedback.hidden = true;
  });

  staffFeedback.appendChild(text);
  staffFeedback.appendChild(closeBtn);
  staffFeedback.hidden = false;

  staffToastTimer = setTimeout(() => {
    staffFeedback.hidden = true;
  }, success ? 4000 : 5500);
}

function consumeFlashBanner() {
  try {
    const raw = sessionStorage.getItem(FLASH_KEY);
    if (!raw) return;
    sessionStorage.removeItem(FLASH_KEY);
    const flash = JSON.parse(raw);
    if (flash && flash.message) {
      showStaffFeedback(flash.message, Boolean(flash.success));
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

function attachTwoStepConfirm(button, defaultLabel, confirmLabel, onConfirm) {
  let timer = null;
  const reset = () => {
    if (timer) clearTimeout(timer);
    timer = null;
    button.dataset.armed = 'false';
    button.classList.remove('btn-armed');
    button.textContent = defaultLabel;
  };
  button.addEventListener('click', () => {
    if (button.dataset.armed !== 'true') {
      button.dataset.armed = 'true';
      button.classList.add('btn-armed');
      button.textContent = confirmLabel;
      timer = setTimeout(reset, 3500);
      return;
    }
    reset();
    onConfirm();
  });
}

function enhanceTimestamps() {
  document.querySelectorAll('time[datetime]').forEach((el) => {
    const ms = Date.parse(el.getAttribute('datetime'));
    if (!Number.isNaN(ms)) {
      el.title = `Local: ${new Date(ms).toLocaleString()}`;
    }
  });
}

async function postStaffAction(url, payload) {
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

function setupStaffPagination(tableSelector, pagerId, pageSize, filterFn = null) {
  const pager = document.getElementById(pagerId);
  let page = 1;

  const render = (resetPage = false) => {
    if (resetPage) page = 1;
    const rows = Array.from(document.querySelectorAll(`${tableSelector} tbody tr`));
    const matched = filterFn ? rows.filter(filterFn) : rows;
    const totalPages = Math.max(1, Math.ceil(matched.length / pageSize));
    if (page > totalPages) page = totalPages;
    const start = (page - 1) * pageSize;
    const visibleSet = new Set(matched.slice(start, start + pageSize));
    rows.forEach((r) => { r.hidden = !visibleSet.has(r); });

    if (!pager) return;
    if (matched.length === 0) {
      pager.hidden = true;
      pager.innerHTML = '';
      return;
    }
    pager.hidden = false;
    const from = start + 1;
    const to = Math.min(start + pageSize, matched.length);
    pager.innerHTML = `
      <span class="page-info">Showing ${from}–${to} of ${matched.length}</span>
      <div class="page-controls">
        <button type="button" class="page-btn" data-dir="prev" ${page <= 1 ? 'disabled' : ''}>Prev</button>
        <span class="page-num">${page} / ${totalPages}</span>
        <button type="button" class="page-btn" data-dir="next" ${page >= totalPages ? 'disabled' : ''}>Next</button>
      </div>
    `;
    pager.querySelector('[data-dir="prev"]')?.addEventListener('click', () => {
      if (page > 1) { page -= 1; render(false); }
    });
    pager.querySelector('[data-dir="next"]')?.addEventListener('click', () => {
      if (page < totalPages) { page += 1; render(false); }
    });
  };

  render(true);
  return render;
}

setupStaffPagination('.equipment-table', 'staff-equipment-pagination', 5);

const renderReservations = setupStaffPagination('#reservations-table', 'staff-reservations-pagination', 5, (row) => {
  const status = row.dataset.status || '';
  return currentResFilter === 'all' || status === currentResFilter;
});

const renderLoans = setupStaffPagination('#loan-history-table', 'staff-loans-pagination', 6, (row) => {
  const query = (loanSearchInput?.value || '').trim().toLowerCase();
  const status = (row.cells[2]?.textContent || '').trim().toLowerCase();
  const text = (row.textContent || '').toLowerCase();
  const statusMatch = currentLoanFilter === 'all' || status === currentLoanFilter;
  const searchMatch = !query || text.includes(query);
  return statusMatch && searchMatch;
});

document.querySelectorAll('[data-res-filter]').forEach((btn) => {
  btn.addEventListener('click', () => {
    currentResFilter = btn.dataset.resFilter;
    document.querySelectorAll('[data-res-filter]').forEach((b) => b.classList.toggle('is-active', b === btn));
    renderReservations(true);
  });
});

document.querySelectorAll('[data-loan-filter]').forEach((btn) => {
  btn.addEventListener('click', () => {
    currentLoanFilter = btn.dataset.loanFilter;
    document.querySelectorAll('[data-loan-filter]').forEach((b) => b.classList.toggle('is-active', b === btn));
    renderLoans(true);
  });
});

if (loanSearchInput) {
  loanSearchInput.addEventListener('input', () => renderLoans(true));
}

if (staffClaimForm) {
  staffClaimForm.addEventListener('submit', async (event) => {
    event.preventDefault();
    const {response, data} = await postStaffAction(staffClaimForm.action, {
      pickup_code: staffPickupInput.value
    });
    if (!response.ok) {
      showStaffFeedback(data.message || 'Unable to claim pickup code.', false);
      return;
    }
    saveFlashAndReload(data.message || 'Equipment handed out.');
  });
}

document.querySelectorAll('.staff-row-claim').forEach((btn) => {
  btn.addEventListener('click', async () => {
    btn.disabled = true;
    const {response, data} = await postStaffAction('/api/reservations/claim', {
      pickup_code: btn.dataset.pickupCode
    });
    if (!response.ok) {
      btn.disabled = false;
      showStaffFeedback(data.message || 'Unable to claim reservation.', false);
      return;
    }
    saveFlashAndReload(data.message || 'Reservation claimed.');
  });
});

document.querySelectorAll('.staff-row-cancel').forEach((btn) => {
  attachTwoStepConfirm(btn, 'Cancel', 'Confirm?', async () => {
    btn.disabled = true;
    const {response, data} = await postStaffAction('/api/reservations/cancel', {
      pickup_code: btn.dataset.pickupCode
    });
    if (!response.ok) {
      btn.disabled = false;
      showStaffFeedback(data.message || 'Unable to cancel reservation.', false);
      return;
    }
    saveFlashAndReload(data.message || 'Reservation cancelled.');
  });
});

const staffConfirmModal = document.getElementById('staff-confirm-modal');
const staffConfirmTitle = document.getElementById('staff-confirm-title');
const staffConfirmMessage = document.getElementById('staff-confirm-message');
const staffConfirmOkBtn = document.getElementById('staff-confirm-ok');
const staffConfirmCancelBtn = document.getElementById('staff-confirm-cancel');
const staffConfirmCloseX = document.getElementById('staff-confirm-x');
let pendingStaffConfirmAction = null;

function closeStaffConfirmModal() {
  pendingStaffConfirmAction = null;
  if (staffConfirmOkBtn) staffConfirmOkBtn.disabled = false;
  if (staffConfirmModal?.open) staffConfirmModal.close();
}

function openStaffConfirmModal({title, message, confirmLabel = 'Confirm', danger = false, onConfirm}) {
  if (!staffConfirmModal || typeof staffConfirmModal.showModal !== 'function') {
    onConfirm();
    return;
  }
  pendingStaffConfirmAction = onConfirm;
  staffConfirmTitle.textContent = title;
  staffConfirmMessage.textContent = message;
  staffConfirmOkBtn.textContent = confirmLabel;
  staffConfirmOkBtn.className = danger ? 'btn-modal-danger' : 'btn-modal-close';
  staffConfirmOkBtn.disabled = false;
  staffConfirmModal.showModal();
  staffConfirmOkBtn.focus();
}

if (staffConfirmModal) {
  staffConfirmCloseX?.addEventListener('click', closeStaffConfirmModal);
  staffConfirmCancelBtn?.addEventListener('click', closeStaffConfirmModal);
  staffConfirmModal.addEventListener('click', (event) => {
    if (event.target === staffConfirmModal) closeStaffConfirmModal();
  });
  staffConfirmModal.addEventListener('close', () => {
    pendingStaffConfirmAction = null;
    if (staffConfirmOkBtn) staffConfirmOkBtn.disabled = false;
  });
  staffConfirmOkBtn?.addEventListener('click', async () => {
    if (!pendingStaffConfirmAction) return;
    const action = pendingStaffConfirmAction;
    staffConfirmOkBtn.disabled = true;
    await action();
    closeStaffConfirmModal();
  });
}

document.querySelectorAll('.staff-row-return').forEach((btn) => {
  btn.addEventListener('click', () => {
    const cardId = btn.dataset.cardId;
    const loanId = btn.dataset.loanId;
    const itemName = btn.dataset.itemName || 'this equipment';
    openStaffConfirmModal({
      title: 'Confirm Return',
      message: `Confirm returning ${itemName} for card ${cardId}?`,
      confirmLabel: 'Confirm Return',
      danger: false,
      onConfirm: async () => {
        btn.disabled = true;
        const {response, data} = await postStaffAction('/api/return', {
          card_id: cardId,
          loan_id: loanId
        });
        if (!response.ok) {
          btn.disabled = false;
          showStaffFeedback(data.message || 'Unable to return equipment.', false);
          return;
        }
        saveFlashAndReload(`${data.message} (Card ${cardId}).`);
      }
    });
  });
});

function updateReservationCountdowns() {
  document.querySelectorAll('#reservations-table tbody tr[data-status="active"]').forEach((row) => {
    const statusCell = row.querySelector('.status-cell');
    const timeEl = row.querySelector('time[datetime]');
    if (!statusCell || !timeEl) return;
    const ms = Date.parse(timeEl.getAttribute('datetime'));
    if (Number.isNaN(ms)) return;
    const mins = Math.ceil((ms - Date.now()) / 60000);
    let badge = statusCell.querySelector('.expiry-badge');
    if (!badge) {
      badge = document.createElement('span');
      badge.className = 'expiry-badge';
      statusCell.appendChild(badge);
    }
    if (mins <= 0) {
      badge.textContent = 'Expired';
      badge.classList.add('is-expired');
    } else {
      badge.textContent = `${mins}m left`;
      badge.classList.remove('is-expired');
    }
  });
}

consumeFlashBanner();
enhanceTimestamps();
updateReservationCountdowns();
setInterval(updateReservationCountdowns, 30000);

const staffModal = document.getElementById('staff-detail-modal');
const staffModalTitle = document.getElementById('staff-modal-title');
const staffModalSubtitle = document.getElementById('staff-modal-subtitle');
const staffModalBody = document.getElementById('staff-modal-body');
const staffModalClose = document.getElementById('staff-modal-close');
const staffModalDone = document.getElementById('staff-modal-done');

function buildModalTable(headers, rowsData, emptyText) {
  staffModalBody.innerHTML = '';
  if (!rowsData.length) {
    const emptyDiv = document.createElement('div');
    emptyDiv.className = 'empty-panel';
    const p = document.createElement('p');
    p.className = 'empty-note';
    p.textContent = emptyText;
    emptyDiv.appendChild(p);
    staffModalBody.appendChild(emptyDiv);
    return;
  }

  const wrap = document.createElement('div');
  wrap.className = 'table-scroll';
  const table = document.createElement('table');
  table.className = 'loan-table compact-table';

  const thead = document.createElement('thead');
  const headTr = document.createElement('tr');
  headers.forEach((label) => {
    const th = document.createElement('th');
    th.scope = 'col';
    th.textContent = label;
    headTr.appendChild(th);
  });
  thead.appendChild(headTr);
  table.appendChild(thead);

  const tbody = document.createElement('tbody');
  rowsData.forEach((cells) => {
    const tr = document.createElement('tr');
    cells.forEach((cell) => {
      const td = document.createElement('td');
      if (cell && typeof cell === 'object') {
        if (cell.code) {
          const code = document.createElement('code');
          code.className = 'table-code';
          code.textContent = cell.text;
          td.appendChild(code);
        } else {
          td.textContent = cell.text;
        }
        if (cell.className) td.className = cell.className;
      } else {
        td.textContent = String(cell);
      }
      tr.appendChild(td);
    });
    tbody.appendChild(tr);
  });
  table.appendChild(tbody);
  wrap.appendChild(table);
  staffModalBody.appendChild(wrap);
}

function openSummaryModal(kind) {
  if (!staffModal) return;

  if (kind === 'available') {
    const rows = Array.from(document.querySelectorAll('.equipment-table tbody tr'))
      .map((row) => ({
        name: (row.cells[0]?.textContent || '').trim(),
        qty: Number(row.cells[1]?.textContent || '0'),
      }))
      .filter((item) => item.qty > 0);
    const total = rows.reduce((sum, item) => sum + item.qty, 0);
    staffModalTitle.textContent = 'Available Units';
    staffModalSubtitle.textContent = `${total} units currently available across ${rows.length} equipment types.`;
    buildModalTable(
      ['Equipment', 'Available units'],
      rows.map((item) => [item.name, String(item.qty)]),
      'No equipment units are currently available.'
    );
  } else if (kind === 'active_loans') {
    const rows = Array.from(document.querySelectorAll('#loan-history-table tbody tr'))
      .filter((row) => (row.cells[2]?.textContent || '').trim().toLowerCase() === 'active')
      .map((row) => {
        const isOverdue = row.cells[4]?.classList.contains('cell-overdue');
        return [
          row.cells[0]?.textContent.trim() || '',
          row.cells[1]?.textContent.trim() || '',
          row.cells[3]?.textContent.trim() || '',
          {
            text: row.cells[4]?.textContent.trim() || '',
            className: isOverdue ? 'cell-overdue' : '',
          },
        ];
      });
    staffModalTitle.textContent = 'Active Loans';
    staffModalSubtitle.textContent = `${rows.length} equipment item(s) currently checked out.`;
    buildModalTable(
      ['Equipment', 'Test card ID', 'Borrowed (UTC)', 'Due (UTC)'],
      rows,
      'No active loans at the moment.'
    );
  } else if (kind === 'active_reservations') {
    const rows = Array.from(document.querySelectorAll('#reservations-table tbody tr'))
      .filter((row) => row.dataset.status === 'active')
      .map((row) => [
        {text: row.cells[0]?.textContent.trim() || '', code: true},
        row.cells[1]?.textContent.trim() || '',
        row.cells[2]?.textContent.trim() || '',
        row.cells[4]?.textContent.trim() || '',
      ]);
    staffModalTitle.textContent = 'Active Reservations';
    staffModalSubtitle.textContent = `${rows.length} reservation(s) currently waiting for pickup.`;
    buildModalTable(
      ['Pickup code', 'Equipment', 'Test card ID', 'Expires (UTC)'],
      rows,
      'No active reservations waiting for pickup.'
    );
  } else if (kind === 'overdue_loans') {
    const rows = Array.from(document.querySelectorAll('#loan-history-table tbody tr'))
      .filter((row) => row.cells[4]?.classList.contains('cell-overdue'))
      .map((row) => [
        row.cells[0]?.textContent.trim() || '',
        row.cells[1]?.textContent.trim() || '',
        row.cells[3]?.textContent.trim() || '',
        {text: row.cells[4]?.textContent.trim() || '', className: 'cell-overdue'},
      ]);
    staffModalTitle.textContent = 'Overdue Loans';
    staffModalSubtitle.textContent = `${rows.length} active loan(s) past the 2-hour return window.`;
    buildModalTable(
      ['Equipment', 'Test card ID', 'Borrowed (UTC)', 'Due (UTC)'],
      rows,
      'No overdue loans.'
    );
  }

  staffModal.showModal();
}

document.querySelectorAll('[data-summary-modal]').forEach((btn) => {
  btn.addEventListener('click', () => openSummaryModal(btn.dataset.summaryModal));
});

if (staffModalClose) staffModalClose.addEventListener('click', () => staffModal.close());
if (staffModalDone) staffModalDone.addEventListener('click', () => staffModal.close());
if (staffModal) {
  staffModal.addEventListener('click', (event) => {
    if (event.target === staffModal) staffModal.close();
  });
}
