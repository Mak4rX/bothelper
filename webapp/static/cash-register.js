export const CASH_DENOMINATIONS = [
  100000, 50000, 20000, 10000, 5000, 2000, 1000, 500, 200, 100, 50,
];

export const CASH_INVENTORY_VERSION = 1;

export function emptyInventory() {
  return Object.fromEntries(CASH_DENOMINATIONS.map((denom) => [String(denom), 0]));
}

export function normalizeInventory(raw) {
  const normalized = emptyInventory();
  const source = raw && typeof raw === 'object' ? raw : {};

  for (const denom of CASH_DENOMINATIONS) {
    const value = Number(source[String(denom)] ?? 0);
    normalized[String(denom)] = Number.isInteger(value) && value >= 0 ? value : 0;
  }

  return normalized;
}

export function inventoryTotal(counts) {
  const normalized = normalizeInventory(counts);
  return CASH_DENOMINATIONS.reduce(
    (total, denom) => total + denom * normalized[String(denom)],
    0,
  );
}

/**
 * Знаходить точну решту з обмеженої кількості купюр і монет.
 * Серед усіх рішень обирає те, де найменше одиниць готівки.
 */
export function makeLimitedChange(amount, availableCounts) {
  if (!Number.isInteger(amount) || amount < 0) {
    return { possible: false, reason: 'invalid_amount', breakdown: [] };
  }
  if (amount === 0) {
    return { possible: true, breakdown: [], itemCount: 0 };
  }
  if (amount % 50 !== 0) {
    return { possible: false, reason: 'unsupported_fraction', breakdown: [] };
  }

  const counts = normalizeInventory(availableCounts);
  if (amount > inventoryTotal(counts)) {
    return { possible: false, reason: 'insufficient_denominations', breakdown: [] };
  }

  const unit = 50;
  const target = amount / unit;
  const items = [];

  // Двійкове розкладання перетворює bounded coin change на 0/1 knapsack.
  // Кількість понад потрібну для target не впливає на можливе рішення.
  for (const denom of CASH_DENOMINATIONS) {
    let remaining = Math.min(counts[String(denom)], Math.floor(amount / denom));
    let bundle = 1;
    while (remaining > 0) {
      const quantity = Math.min(bundle, remaining);
      items.push({ denom, quantity, weight: (denom / unit) * quantity });
      remaining -= quantity;
      bundle *= 2;
    }
  }

  const dp = new Array(target + 1).fill(null);
  dp[0] = { cost: 0, node: null };

  for (const item of items) {
    for (let sum = target; sum >= item.weight; sum--) {
      const previous = dp[sum - item.weight];
      if (!previous) continue;
      const candidateCost = previous.cost + item.quantity;
      if (!dp[sum] || candidateCost < dp[sum].cost) {
        dp[sum] = {
          cost: candidateCost,
          node: { item, previous: previous.node },
        };
      }
    }
  }

  if (!dp[target]) {
    return { possible: false, reason: 'insufficient_denominations', breakdown: [] };
  }

  const used = emptyInventory();
  for (let node = dp[target].node; node; node = node.previous) {
    used[String(node.item.denom)] += node.item.quantity;
  }

  const breakdown = CASH_DENOMINATIONS
    .filter((denom) => used[String(denom)] > 0)
    .map((denom) => ({ denom, count: used[String(denom)] }));

  return { possible: true, breakdown, itemCount: dp[target].cost };
}

export function addInventories(baseCounts, addedCounts) {
  const base = normalizeInventory(baseCounts);
  const added = normalizeInventory(addedCounts);
  return Object.fromEntries(
    CASH_DENOMINATIONS.map((denom) => [
      String(denom),
      base[String(denom)] + added[String(denom)],
    ]),
  );
}

export function applyCashTransaction(currentCounts, receivedCounts, changeBreakdown) {
  const next = addInventories(currentCounts, receivedCounts);

  for (const row of changeBreakdown || []) {
    const denom = Number(row.denom);
    const count = Number(row.count);
    if (!CASH_DENOMINATIONS.includes(denom) || !Number.isInteger(count) || count < 0) {
      throw new Error('Некоректний склад решти');
    }
    const key = String(denom);
    if (next[key] < count) {
      throw new Error('Недостатньо купюр для видачі решти');
    }
    next[key] -= count;
  }

  return next;
}

export const CASH_HISTORY_STORAGE_KEY = 'cyberhelper.cashHistory.v1';
export const MAX_CASH_HISTORY_ENTRIES = 100;

export function createCashSnapshot(counts, note = '', timestamp = null) {
  const normalized = normalizeInventory(counts);
  const ts = timestamp || new Date().toISOString();
  return {
    id: `cash_${Date.now()}_${Math.random().toString(36).slice(2, 6)}`,
    timestamp: ts,
    total: inventoryTotal(normalized),
    counts: normalized,
    note: typeof note === 'string' ? note.trim() : '',
  };
}

export function getDenominationBreakdown(counts) {
  const normalized = normalizeInventory(counts);
  const items = [];
  let totalItems = 0;
  for (const denom of CASH_DENOMINATIONS) {
    const qty = normalized[String(denom)] || 0;
    if (qty > 0) {
      const subtotal = denom * qty;
      const label = denom >= 100 ? `${denom / 100}₴` : `${denom}к`;
      items.push({
        denom,
        label,
        count: qty,
        subtotal,
      });
      totalItems += qty;
    }
  }
  return {
    items,
    totalItems,
    totalAmount: inventoryTotal(normalized),
  };
}

export function formatMoneyUah(kopiykas) {
  const isNegative = kopiykas < 0;
  const abs = Math.abs(kopiykas);
  const uah = abs / 100;
  const parts = (uah % 1 === 0 ? String(uah) : uah.toFixed(2)).split('.');
  parts[0] = parts[0].replace(/\B(?=(\d{3})+(?!\d))/g, ' ');
  const formatted = parts.join('.');
  return `${isNegative ? '-' : ''}${formatted} грн`;
}

export function calculateDiff(currentTotal, previousTotal) {
  if (typeof previousTotal !== 'number') {
    return { diff: 0, sign: 'none', text: 'Перший запис' };
  }
  const diff = currentTotal - previousTotal;
  if (diff > 0) {
    return { diff, sign: 'plus', text: `+${formatMoneyUah(diff)}` };
  } else if (diff < 0) {
    return { diff, sign: 'minus', text: formatMoneyUah(diff) };
  }
  return { diff: 0, sign: 'zero', text: '0 грн' };
}

if (typeof window !== 'undefined') {
  window.CashRegister = {
    CASH_DENOMINATIONS,
    CASH_INVENTORY_VERSION,
    CASH_HISTORY_STORAGE_KEY,
    MAX_CASH_HISTORY_ENTRIES,
    emptyInventory,
    normalizeInventory,
    inventoryTotal,
    makeLimitedChange,
    addInventories,
    applyCashTransaction,
    createCashSnapshot,
    getDenominationBreakdown,
    formatMoneyUah,
    calculateDiff,
  };
}
