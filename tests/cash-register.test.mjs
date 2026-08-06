import test from 'node:test';
import assert from 'node:assert/strict';

import {
  CASH_DENOMINATIONS,
  emptyInventory,
  normalizeInventory,
  inventoryTotal,
  makeLimitedChange,
  addInventories,
  applyCashTransaction,
} from '../webapp/static/cash-register.js';

function inventory(entries = {}) {
  return normalizeInventory(entries);
}

test('порожня каса містить усі номінали', () => {
  const cash = emptyInventory();
  assert.deepEqual(Object.keys(cash).map(Number).sort((a, b) => b - a), CASH_DENOMINATIONS);
  assert.equal(inventoryTotal(cash), 0);
});

test('некоректні кількості нормалізуються до нуля', () => {
  const cash = normalizeInventory({ 10000: 2, 5000: -1, 2000: 1.5, x: 99 });
  assert.equal(cash['10000'], 2);
  assert.equal(cash['5000'], 0);
  assert.equal(cash['2000'], 0);
  assert.equal(cash.x, undefined);
});

test('рахується повна сума каси', () => {
  assert.equal(inventoryTotal(inventory({ 10000: 2, 5000: 1, 50: 3 })), 25150);
});

test('точна решта використовує наявні купюри', () => {
  const result = makeLimitedChange(7000, inventory({ 5000: 1, 2000: 1 }));
  assert.equal(result.possible, true);
  assert.deepEqual(result.breakdown, [
    { denom: 5000, count: 1 },
    { denom: 2000, count: 1 },
  ]);
});

test('обирається мінімальна кількість купюр', () => {
  const result = makeLimitedChange(10000, inventory({ 10000: 1, 5000: 2, 2000: 5 }));
  assert.deepEqual(result.breakdown, [{ denom: 10000, count: 1 }]);
  assert.equal(result.itemCount, 1);
});

test('обмежений алгоритм знаходить не жадібний варіант', () => {
  const result = makeLimitedChange(6000, inventory({ 5000: 1, 2000: 3 }));
  assert.equal(result.possible, true);
  assert.deepEqual(result.breakdown, [{ denom: 2000, count: 3 }]);
});

test('при невідповідних номіналах операція неможлива', () => {
  const result = makeLimitedChange(3000, inventory({ 5000: 10 }));
  assert.equal(result.possible, false);
  assert.equal(result.reason, 'insufficient_denominations');
});

test('сума менша 50 копійок не підтримується', () => {
  const result = makeLimitedChange(30, inventory({ 50: 1 }));
  assert.equal(result.possible, false);
  assert.equal(result.reason, 'unsupported_fraction');
});

test('отримані купюри доступні для видачі решти', () => {
  const current = inventory({ 5000: 1 });
  const received = inventory({ 20000: 1, 10000: 1 });
  const available = addInventories(current, received);
  const plan = makeLimitedChange(10000, available);
  assert.deepEqual(plan.breakdown, [{ denom: 10000, count: 1 }]);
});

test('операція додає отримане і списує решту', () => {
  const before = inventory({ 5000: 1 });
  const received = inventory({ 20000: 1 });
  const next = applyCashTransaction(before, received, [
    { denom: 5000, count: 1 },
  ]);
  assert.equal(next['20000'], 1);
  assert.equal(next['5000'], 0);
  assert.equal(inventoryTotal(next), inventoryTotal(before) + 20000 - 5000);
  assert.ok(Object.values(next).every((count) => count >= 0));
});

test('не можна списати більше купюр, ніж є', () => {
  assert.throws(
    () => applyCashTransaction(inventory(), inventory(), [{ denom: 5000, count: 1 }]),
    /Недостатньо купюр/,
  );
});
