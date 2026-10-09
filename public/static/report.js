/**
 * Звіт «Закриття зміни»: формули і текст.
 *
 * Усі суми рахуються цілими копійками — float для грошей не використовується
 * (0.1 + 0.2 дає 0.30000000000000004, а це каса). Вхід і вихід buildReport — гривні
 * (не більше двох знаків після коми).
 */

export const SCHEMES = {
  day: {
    title: 'Денна зміна',
    openLabel: 'Каса готівки зранку',
    earnedLabel: 'Зароблено за день готівки',
    closeLabel: 'Каса готівки ввечері',
  },
  night: {
    title: 'Нічна зміна',
    openLabel: 'Каса готівки вечері',
    earnedLabel: 'Зароблено за ніч готівки',
    closeLabel: 'Каса готівки зранку',
  },
};

/** Гривні (можливо з копійками) → цілі копійки. */
export function toKopecks(hryvnias) {
  return Math.round(hryvnias * 100);
}

/**
 * Копійки → «11 142,50». Роздільник тисяч — звичайний пробіл (текст копіюють
 * у месенджер), копійки не показуємо, коли їх 0.
 */
export function formatMoney(kopecks) {
  const sign = kopecks < 0 ? '-' : '';
  const abs = Math.abs(Math.trunc(kopecks));
  const hryvnias = Math.floor(abs / 100);
  const rest = abs % 100;
  const whole = String(hryvnias).replace(/\B(?=(\d{3})+(?!\d))/g, ' ');
  return rest ? `${sign}${whole},${String(rest).padStart(2, '0')}` : `${sign}${whole}`;
}

/**
 * Зароблено = кінцева каса − початкова + витрати + інкасація.
 * Надлишок  = зароблено − сенет (плюс — надлишок, мінус — недостача).
 *
 * @returns {{text: string, earned: number, surplus: number}} earned і surplus — гривні
 */
export function buildReport({ shift, openCash, closeCash, expenses = 0, collection = 0, senet = 0, note = '' }) {
  const scheme = SCHEMES[shift];
  if (!scheme) throw new Error(`Unknown shift: ${shift}`);

  const open = toKopecks(openCash);
  const close = toKopecks(closeCash);
  const spent = toKopecks(expenses);
  const collected = toKopecks(collection);

  const earned = close - open + spent + collected;
  const surplus = earned - toKopecks(senet);

  const lines = [
    'Закриття зміни.',
    `${scheme.openLabel}: ${formatMoney(open)}`,
    `${scheme.earnedLabel}: ${formatMoney(earned)}`,
    `Торгівельні витрати: ${formatMoney(spent)}`,
  ];
  if (collected) lines.push(`Інкасація: ${formatMoney(collected)}`);
  lines.push(`${scheme.closeLabel}: ${formatMoney(close)}`);

  const trimmed = (note || '').trim();
  const noteSuffix = trimmed ? `, ${trimmed}` : '';

  if (surplus > 0) {
    lines.push(`${formatMoney(surplus)} грн надлишку${noteSuffix}.`);
  } else if (surplus < 0) {
    lines.push(`${formatMoney(-surplus)} грн недостачі${noteSuffix}.`);
  } else {
    lines.push(`Надлишок: 0 грн${noteSuffix}`);
  }

  return { text: lines.join('\n'), earned: earned / 100, surplus: surplus / 100 };
}

// Інлайнові обробники в index.html викликають функції через глобальний обʼєкт.
if (typeof window !== 'undefined') {
  window.ShiftReport = { buildReport, formatMoney, toKopecks, SCHEMES };
}
