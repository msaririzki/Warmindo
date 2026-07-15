// ===== JOKIAN WARMINDO — MAIN JS =====

// ==============================
// TOAST NOTIFICATION SYSTEM
// ==============================
function showToast(message, type = 'success', duration = 3000) {
  const container = document.getElementById('toast-container');
  if (!container) return;

  const icons = {
    success: `<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/></svg>`,
    error:   `<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/></svg>`,
    info:    `<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>`,
    warning: `<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"/></svg>`,
  };
  const colors = {
    success: 'bg-green-500',
    error:   'bg-red-500',
    info:    'bg-blue-500',
    warning: 'bg-yellow-500',
  };

  const toast = document.createElement('div');
  toast.className = `toast flex items-center gap-3 px-4 py-3 rounded-xl text-white shadow-lg ${colors[type]} min-w-[260px] max-w-xs`;
  toast.innerHTML = `${icons[type]}<span class="text-sm font-medium flex-1">${message}</span>`;
  container.appendChild(toast);

  setTimeout(() => {
    toast.classList.add('hide');
    setTimeout(() => toast.remove(), 350);
  }, duration);
}

// ==============================
// CART SYSTEM (localStorage)
// ==============================
const Cart = {
  key: 'jokian_cart',

  getAll() {
    try { return JSON.parse(localStorage.getItem(this.key)) || []; }
    catch { return []; }
  },

  save(items) {
    localStorage.setItem(this.key, JSON.stringify(items));
    this.updateUI();
  },

  add(item) {
    const items = this.getAll();
    const idx = items.findIndex(i => i.id === item.id && i.varian === item.varian);
    if (idx > -1) {
      items[idx].qty += item.qty;
    } else {
      items.push(item);
    }
    this.save(items);
    showToast(`${item.nama} ditambahkan ke keranjang! 🛒`, 'success');
  },

  remove(index) {
    const items = this.getAll();
    items.splice(index, 1);
    this.save(items);
  },

  updateQty(index, qty) {
    const items = this.getAll();
    if (qty <= 0) { this.remove(index); return; }
    items[index].qty = qty;
    this.save(items);
  },

  clear() {
    localStorage.removeItem(this.key);
    this.updateUI();
  },

  total() {
    return this.getAll().reduce((s, i) => s + (i.harga * i.qty), 0);
  },

  count() {
    return this.getAll().reduce((s, i) => s + i.qty, 0);
  },

  updateUI() {
    const count = this.count();
    const total = this.total();
    const badges = document.querySelectorAll('.cart-badge');
    const totals = document.querySelectorAll('.cart-total-display');
    const btns   = document.querySelectorAll('.floating-cart-btn');

    badges.forEach(b => {
      b.textContent = count;
      b.classList.toggle('hidden', count === 0);
    });
    totals.forEach(t => { t.textContent = formatRupiah(total); });
    btns.forEach(b => { b.classList.toggle('hidden', count === 0); });
  }
};

// ==============================
// FORMAT RUPIAH
// ==============================
function formatRupiah(num) {
  return 'Rp ' + Number(num).toLocaleString('id-ID');
}

// ==============================
// MODAL SYSTEM
// ==============================
function openModal(id) {
  const modal = document.getElementById(id);
  if (!modal) return;
  modal.classList.remove('hidden');
  document.body.style.overflow = 'hidden';
  setTimeout(() => modal.querySelector('.modal-box')?.classList.add('scale-100', 'opacity-100'), 10);
}

function closeModal(id) {
  const modal = document.getElementById(id);
  if (!modal) return;
  modal.classList.add('hidden');
  document.body.style.overflow = '';
}

// Close modal on overlay click
document.addEventListener('click', e => {
  if (e.target.classList.contains('modal-overlay')) {
    e.target.closest('[id]')?.classList.add('hidden');
    document.body.style.overflow = '';
  }
});

// ==============================
// STORE STATUS (jam operasional)
// ==============================
function checkStoreStatus(jamBuka = '07:00', jamTutup = '22:00', overrideStatus = null) {
  if (overrideStatus !== null) return overrideStatus;
  const now = new Date();
  const [bH, bM] = jamBuka.split(':').map(Number);
  const [tH, tM] = jamTutup.split(':').map(Number);
  const nowMins  = now.getHours() * 60 + now.getMinutes();
  const bukaMins = bH * 60 + bM;
  const tutupMins= tH * 60 + tM;
  return nowMins >= bukaMins && nowMins < tutupMins;
}

function renderStoreStatus(el, isOpen) {
  if (!el) return;
  el.innerHTML = isOpen
    ? `<span class="inline-flex items-center gap-1.5 bg-green-100 text-green-700 text-sm font-semibold px-3 py-1 rounded-full border border-green-300">
         <span class="w-2 h-2 bg-green-500 rounded-full animate-pulse"></span> Buka Sekarang
       </span>`
    : `<span class="inline-flex items-center gap-1.5 bg-red-100 text-red-700 text-sm font-semibold px-3 py-1 rounded-full border border-red-300">
         <span class="w-2 h-2 bg-red-500 rounded-full"></span> Tutup
       </span>`;
}

// ==============================
// FILTER MENU (client-side)
// ==============================
function filterMenuByCategory(cat) {
  const cards = document.querySelectorAll('[data-kategori]');
  cards.forEach(c => {
    const match = cat === 'semua' || c.dataset.kategori === cat;
    c.style.display = match ? '' : 'none';
  });
}

function searchMenu(query) {
  const q = query.toLowerCase().trim();
  const cards = document.querySelectorAll('[data-nama]');
  cards.forEach(c => {
    const match = q === '' || c.dataset.nama.toLowerCase().includes(q);
    c.style.display = match ? '' : 'none';
  });
}

// ==============================
// POLLING (status pesanan)
// ==============================
function startPolling(url, interval = 5000, onUpdate) {
  const poll = () => {
    fetch(url)
      .then(r => r.json())
      .then(data => onUpdate(data))
      .catch(() => {});
  };
  poll();
  return setInterval(poll, interval);
}

// ==============================
// NUMBER FORMATTER INPUT
// ==============================
function initRupiahInput(el) {
  if (!el) return;
  el.addEventListener('input', () => {
    let val = el.value.replace(/\D/g, '');
    el.value = val ? Number(val).toLocaleString('id-ID') : '';
  });
}

// ==============================
// INIT ON LOAD
// ==============================
document.addEventListener('DOMContentLoaded', () => {
  Cart.updateUI();

  // Store status init
  const statusEl = document.getElementById('store-status');
  if (statusEl) {
    const isOpen = checkStoreStatus('07:00', '22:00');
    renderStoreStatus(statusEl, isOpen);
  }

  // Smooth anchor scroll
  document.querySelectorAll('a[href^="#"]').forEach(a => {
    a.addEventListener('click', e => {
      const target = document.querySelector(a.getAttribute('href'));
      if (target) { e.preventDefault(); target.scrollIntoView({ behavior: 'smooth' }); }
    });
  });
});
