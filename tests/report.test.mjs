import test from 'node:test';
import assert from 'node:assert/strict';

import { buildReport, formatMoney, toKopecks } from '../webapp/static/report.js';

test('інкасація входить у зароблено і виводиться окремим рядком', () => {
  const { text, earned, surplus } = buildReport({
    shift: 'day',
    openCash: 10000,
    closeCash: 8000,
    expenses: 500,
    senet: 3500,
    collection: 5000,
  });
  assert.equal(earned, 3500);
  assert.equal(surplus, 0);
  assert.ok(text.includes('Інкасація: 5 000'));
  assert.ok(text.endsWith('Надлишок: 0 грн'));
});

test('копійки зберігаються у тексті звіту', () => {
  const { text, earned, surplus } = buildReport({
    shift: 'day',
    openCash: 10000,
    closeCash: 11142.5,
    senet: 1142.5,
  });
  assert.equal(earned, 1142.5);
  assert.equal(surplus, 0);
  assert.ok(text.includes('Каса готівки ввечері: 11 142,50'));
});

test('float-пастка: 0.3 − 0.1 − 0.2 дорівнює рівно нулю', () => {
  const { surplus, text } = buildReport({ shift: 'day', openCash: 0.1, closeCash: 0.3, senet: 0.2 });
  assert.equal(surplus, 0);
  assert.ok(text.endsWith('Надлишок: 0 грн'));
});

test('нічна зміна — приклад із README', () => {
  const { text, earned, surplus } = buildReport({
    shift: 'night',
    openCash: 7791,
    closeCash: 8677,
    senet: 883,
  });
  assert.equal(earned, 886);
  assert.equal(surplus, 3);
  assert.equal(
    text,
    [
      'Закриття зміни.',
      'Каса готівки вечері: 7 791',
      'Зароблено за ніч готівки: 886',
      'Торгівельні витрати: 0',
      'Каса готівки зранку: 8 677',
      '3 грн надлишку.',
    ].join('\n'),
  );
});

test('недостача і нотатка', () => {
  const short = buildReport({ shift: 'day', openCash: 100, closeCash: 200, senet: 150, note: '  видав решту  ' });
  assert.equal(short.surplus, -50);
  assert.ok(short.text.endsWith('50 грн недостачі, видав решту.'));

  const over = buildReport({ shift: 'day', openCash: 100, closeCash: 200, senet: 90, note: 'ок' });
  assert.ok(over.text.endsWith('10 грн надлишку, ок.'));

  const zero = buildReport({ shift: 'day', openCash: 100, closeCash: 200, senet: 100, note: 'ок' });
  assert.ok(zero.text.endsWith('Надлишок: 0 грн, ок'));
});

test('невідома зміна — помилка', () => {
  assert.throws(() => buildReport({ shift: 'evening', openCash: 0, closeCash: 0 }), /Unknown shift/);
});

test('formatMoney', () => {
  assert.equal(formatMoney(779100), '7 791');
  assert.equal(formatMoney(1114250), '11 142,50');
  assert.equal(formatMoney(-50), '-0,50');
  assert.equal(formatMoney(-1234560), '-12 345,60');
  assert.equal(formatMoney(0), '0');
});

test('toKopecks округлює до копійки', () => {
  assert.equal(toKopecks(11142.5), 1114250);
  assert.equal(toKopecks(0.07), 7);
  assert.equal(toKopecks(1.005), 100); // 1.005 у float — 1.00499…, це не копійкова сума
});
