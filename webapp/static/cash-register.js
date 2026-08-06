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

if (typeof window !== 'undefined') {
  window.CashRegister = {
    CASH_DENOMINATIONS,
    CASH_INVENTORY_VERSION,
    emptyInventory,
    normalizeInventory,
    inventoryTotal,
    makeLimitedChange,
    addInventories,
    applyCashTransaction,
  };
}
