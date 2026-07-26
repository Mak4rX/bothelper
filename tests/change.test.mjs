import test from 'node:test';
import assert from 'node:assert/strict';

import {
  parseExpression,
  ParseError,
  makeChange,
  formatUah,
  DENOMINATIONS,
} from '../webapp/static/change.js';

// parseExpression повертає копійки цілим числом.

test('додавання', () => {
  assert.equal(parseExpression('50+100'), 15000);
});

test('множення: три години по 70', () => {
  assert.equal(parseExpression('3*70'), 21000);
});

test('множення має вищий пріоритет за додавання', () => {
  assert.equal(parseExpression('2+3*4'), 1400);
});

test('дужки змінюють пріоритет', () => {
  assert.equal(parseExpression('(50+100)*2'), 30000);
});

test('змішаний вираз', () => {
  assert.equal(parseExpression('2*80+50'), 21000);
});

test('віднімання', () => {
  assert.equal(parseExpression('200-50'), 15000);
});

test('ділення', () => {
  assert.equal(parseExpression('100/4'), 2500);
});

test('унарний мінус на початку', () => {
  assert.equal(parseExpression('-50+100'), 5000);
});

test('пробіли ігноруються — 8 680 це вісім тисяч шістсот вісімдесят', () => {
  assert.equal(parseExpression('8 680'), 868000);
});

test('кома як десятковий роздільник', () => {
  assert.equal(parseExpression('50,5'), 5050);
});

test('крапка як десятковий роздільник', () => {
  assert.equal(parseExpression('50.5'), 5050);
});

test('дробова частина обрізається до копійок', () => {
  assert.equal(parseExpression('50,567'), 5056);
});

test('× як синонім множення', () => {
  assert.equal(parseExpression('3×70'), 21000);
});

test('÷ як синонім ділення', () => {
  assert.equal(parseExpression('100÷4'), 2500);
});

test('знак після бінарного оператора допускається', () => {
  assert.equal(parseExpression('50++100'), 15000);
  assert.equal(parseExpression('50--100'), 15000);
});

test('копійки рахуються точно, без похибки float', () => {
  // 0.1 + 0.2 у float дає 0.30000000000000004
  assert.equal(parseExpression('0,1+0,2'), 30);
});

test('порожній ввід повертає null', () => {
  assert.equal(parseExpression(''), null);
  assert.equal(parseExpression('   '), null);
});

test('оператор без правого операнда — помилка', () => {
  assert.throws(() => parseExpression('50+'), ParseError);
});

test('незакрита дужка — помилка', () => {
  assert.throws(() => parseExpression('(50'), ParseError);
});

test('зайва закриваюча дужка — помилка', () => {
  assert.throws(() => parseExpression('50)'), ParseError);
});

test('порожні дужки — помилка', () => {
  assert.throws(() => parseExpression('()'), ParseError);
});

test('ділення на нуль — помилка', () => {
  assert.throws(() => parseExpression('5/0'), ParseError);
});

test('літери — помилка', () => {
  assert.throws(() => parseExpression('abc'), ParseError);
});

test('два бінарні оператори поспіль — помилка', () => {
  assert.throws(() => parseExpression('50+*100'), ParseError);
});

test('помилка знає позицію в рядку', () => {
  assert.throws(
    () => parseExpression('50+abc'),
    (err) => err instanceof ParseError && err.position === 3,
  );
});

// ---------- makeChange ----------

test('решта 100 ₴ — одна купюра', () => {
  const { rounded, wasRounded, breakdown } = makeChange(10000);
  assert.equal(rounded, 10000);
  assert.equal(wasRounded, false);
  assert.deepEqual(breakdown, [{ denom: 10000, count: 1 }]);
});

test('решта 137 ₴ розкладається мінімумом купюр', () => {
  const { breakdown } = makeChange(13700);
  assert.deepEqual(breakdown, [
    { denom: 10000, count: 1 },
    { denom: 2000, count: 1 },
    { denom: 1000, count: 1 },
    { denom: 500, count: 1 },
    { denom: 200, count: 1 },
  ]);
});

test('однакові номінали групуються в один рядок', () => {
  const { breakdown } = makeChange(6000); // 60 ₴ = 50 + 10
  assert.deepEqual(breakdown, [
    { denom: 5000, count: 1 },
    { denom: 1000, count: 1 },
  ]);
});

test('решта 40 ₴ — дві двадцятки', () => {
  const { breakdown } = makeChange(4000);
  assert.deepEqual(breakdown, [{ denom: 2000, count: 2 }]);
});

test('решта 50 копійок — одна монета', () => {
  const { rounded, wasRounded, breakdown } = makeChange(50);
  assert.equal(rounded, 50);
  assert.equal(wasRounded, false);
  assert.deepEqual(breakdown, [{ denom: 50, count: 1 }]);
});

test('нульова решта — порожня розбивка', () => {
  const { rounded, wasRounded, breakdown } = makeChange(0);
  assert.equal(rounded, 0);
  assert.equal(wasRounded, false);
  assert.deepEqual(breakdown, []);
});

test('3 копійки заокруглюються вниз до нуля', () => {
  const { rounded, wasRounded, breakdown } = makeChange(3);
  assert.equal(rounded, 0);
  assert.equal(wasRounded, true);
  assert.deepEqual(breakdown, []);
});

test('7 копійок заокруглюються вгору до 10', () => {
  const { rounded, wasRounded, breakdown } = makeChange(7);
  assert.equal(rounded, 10);
  assert.equal(wasRounded, true);
  assert.deepEqual(breakdown, [{ denom: 10, count: 1 }]);
});

test('5 копійок заокруглюються вгору — правило НБУ', () => {
  const { rounded, wasRounded } = makeChange(5);
  assert.equal(rounded, 10);
  assert.equal(wasRounded, true);
});

test('4 копійки заокруглюються вниз', () => {
  const { rounded, wasRounded } = makeChange(4);
  assert.equal(rounded, 0);
  assert.equal(wasRounded, true);
});

test('розбивка завжди дає рівно заокруглену суму', () => {
  for (let kop = 0; kop <= 300000; kop += 7) {
    const { rounded, breakdown } = makeChange(kop);
    const sum = breakdown.reduce((acc, r) => acc + r.denom * r.count, 0);
    assert.equal(sum, rounded, `розбивка ${kop} коп не сходиться`);
  }
});

test('жадібна розбивка мінімальна — звірено з динамічним програмуванням', () => {
  // Ризик зі специфікації: перевіряємо перебором, а не на віру.
  const LIMIT = 300000; // до 3000 ₴ у кроках по 10 коп
  const steps = LIMIT / 10;
  const best = new Array(steps + 1).fill(Infinity);
  best[0] = 0;
  for (let s = 1; s <= steps; s++) {
    for (const denom of DENOMINATIONS) {
      const d = denom / 10;
      if (d <= s && best[s - d] + 1 < best[s]) best[s] = best[s - d] + 1;
    }
  }
  for (let s = 0; s <= steps; s++) {
    const { breakdown } = makeChange(s * 10);
    const greedy = breakdown.reduce((acc, r) => acc + r.count, 0);
    assert.equal(greedy, best[s], `${s * 10} коп: жадібно ${greedy}, оптимально ${best[s]}`);
  }
});

// ---------- formatUah ----------

test('ціла сума без копійок', () => {
  assert.equal(formatUah(21000), '210 ₴');
});

test('сума з копійками через кому', () => {
  assert.equal(formatUah(5050), '50,50 ₴');
});

test('копійки без гривень', () => {
  assert.equal(formatUah(10), '0,10 ₴');
});

test('нуль', () => {
  assert.equal(formatUah(0), '0 ₴');
});

test('тисячі розділяються пробілом — як у звітах бота', () => {
  assert.equal(formatUah(868000), '8 680 ₴');
});

test('від\u02bcємна сума', () => {
  assert.equal(formatUah(-3000), '-30 ₴');
});
