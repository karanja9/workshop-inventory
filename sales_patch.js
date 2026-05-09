/**
 * PATCH for index.html — Merge bot sales from GitHub sales_log.json
 * into the web app's Sales view.
 *
 * HOW TO APPLY:
 * In your index.html, find the closing </body> tag and paste this entire
 * <script> block just before it.
 *
 * What it does:
 * - On page load and on every switchView('sales'), fetches sales_log.json
 *   from your GitHub repo (same place the WhatsApp bot writes to)
 * - Merges those records with any locally-recorded sales (from the web app)
 * - Deduplicates by id so records aren't doubled
 * - The merged list is used for display only — localStorage is not overwritten
 */

// ── CONFIG — must match your repo ─────────────────────────────────────────────
const BOT_SALES_URL =
  'https://raw.githubusercontent.com/karanja9/workshop-inventory/main/sales_log.json';
// ──────────────────────────────────────────────────────────────────────────────

// Holds the merged (local + bot) sales array used only for rendering.
// The real `sales` array (localStorage) is untouched.
let mergedSales = [];
let botSalesLoaded = false;

async function fetchBotSales() {
  try {
    const r = await fetch(BOT_SALES_URL + '?t=' + Date.now()); // bust cache
    if (!r.ok) return [];
    const data = await r.json();
    // Normalise bot sale entries to match web-app format
    return data.map(s => ({
      id:        s.id || `bot-${s.sku}-${s.timestamp}`,
      sku:       s.sku,
      name:      s.name,
      category:  s.category || 'General',
      qty:       s.qty,
      price:     s.price,
      total:     s.total,
      timestamp: s.timestamp,
      source:    'bot', // lets us badge these rows differently
    }));
  } catch (e) {
    console.warn('Could not load bot sales_log.json:', e);
    return [];
  }
}

async function loadAndMergeSales() {
  const botSales   = await fetchBotSales();
  // `sales` is the global array populated by the existing loadSales()
  const localSales = window.sales || [];

  // Merge, deduplicate by id
  const seen = new Set();
  mergedSales = [...botSales, ...localSales].filter(s => {
    if (seen.has(s.id)) return false;
    seen.add(s.id);
    return true;
  });

  // Sort newest first
  mergedSales.sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp));
  botSalesLoaded = true;
}

// ── Override the three render functions that use the sales array ───────────────

const _origRenderSalesDashboard = window.renderSalesDashboard;
window.renderSalesDashboard = function () {
  // Swap in mergedSales temporarily
  const orig = window.sales;
  if (botSalesLoaded) window.sales = mergedSales;
  _origRenderSalesDashboard();
  window.sales = orig;
};

const _origRenderSalesRankings = window.renderSalesRankings;
window.renderSalesRankings = function () {
  const orig = window.sales;
  if (botSalesLoaded) window.sales = mergedSales;
  _origRenderSalesRankings();
  window.sales = orig;
};

const _origRenderSalesHistory = window.renderSalesHistory;
window.renderSalesHistory = function () {
  const orig = window.sales;
  if (botSalesLoaded) window.sales = mergedSales;

  // Call original — it will now see bot sales too
  _origRenderSalesHistory();

  window.sales = orig;

  // Badge bot-sourced rows with a small WhatsApp icon
  document.querySelectorAll('#sales-history-body tr').forEach((row, i) => {
    const sale = mergedSales[i]; // rows are in same order as mergedSales
    if (sale && sale.source === 'bot') {
      const skuCell = row.cells[2];
      if (skuCell && !skuCell.querySelector('.bot-badge')) {
        const badge = document.createElement('span');
        badge.className = 'bot-badge';
        badge.title = 'Recorded via WhatsApp bot';
        badge.style.cssText =
          'display:inline-block;margin-left:4px;width:14px;height:14px;' +
          'background:#25d366;border-radius:50%;vertical-align:middle;' +
          'font-size:9px;line-height:14px;text-align:center;color:white;';
        badge.textContent = 'W';
        skuCell.appendChild(badge);
      }
    }
  });
};

// ── Hook into switchView ───────────────────────────────────────────────────────
const _origSwitchView = window.switchView;
window.switchView = function (view) {
  _origSwitchView(view);
  if (view === 'sales') {
    // Reload bot sales fresh every time the Sales tab is opened
    loadAndMergeSales().then(() => {
      renderSalesDashboard();
      renderSalesRankings();
      renderSalesHistory();
    });
  }
};

// ── Also merge on initial dashboard load ──────────────────────────────────────
const _origUpdateDashboard = window.updateDashboard;
window.updateDashboard = function () {
  _origUpdateDashboard();
  // Refresh merged sales in background so badge counts stay accurate
  loadAndMergeSales();
};

// ── Kick off first load ────────────────────────────────────────────────────────
loadAndMergeSales().then(() => {
  if (window.currentView === 'sales') {
    renderSalesDashboard();
    renderSalesRankings();
    renderSalesHistory();
  }
  // Update sidebar badge to include bot sales
  const today = new Date().toDateString();
  const count = mergedSales.filter(
    s => new Date(s.timestamp).toDateString() === today
  ).length;
  const badge = document.getElementById('sidebar-sales-badge');
  if (badge) {
    if (count > 0) { badge.textContent = count; badge.classList.remove('hidden'); }
    else badge.classList.add('hidden');
  }
});
