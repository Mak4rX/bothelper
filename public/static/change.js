/**
 * Калькулятор решти: розбір арифметичного виразу і розмін суми на купюри.
 *
 * Усі суми — цілі копійки. Float для грошей не використовується:
 * 0.1 + 0.2 дає 0.30000000000000004, а це каса.
 */

export class ParseError extends Error {
  /**
   * @param {string} message
   * @param {number} position індекс у вихідному рядку
   */
  constructor(message, position) {
    super(message);
    this.name = 'ParseError';
    this.position = position;
  }
}

/** Заокруглення половини від нуля — симетрично для від'ємних сум. */
function roundHalfAwayFromZero(x) {
  return x < 0 ? -Math.round(-x) : Math.round(x);
}

function isDigit(ch) {
  return ch >= '0' && ch <= '9';
}

/**
 * Прибирає всі пробіли і запам'ятовує, звідки взявся кожен символ,
 * щоб позиція в ParseError вказувала на вихідний рядок.
 */
function stripSpaces(input) {
  let text = '';
  const origin = [];
  for (let i = 0; i < input.length; i++) {
    if (/\s/.test(input[i])) continue;
    text += input[i];
    origin.push(i);
  }
  return { text, origin };
}

/**
 * Розбирає вираз і повертає суму в копійках.
 *
 * Граматика:
 *   expr    := term (('+' | '-') term)*
 *   term    := factor (('*' | '×' | '/' | '÷') factor)*
 *   factor  := ('-' | '+')* primary
 *   primary := number | '(' expr ')'
 *
 * @param {string} input
 * @returns {number | null} копійки, або null якщо введено порожньо
 * @throws {ParseError}
 */
export function parseExpression(input) {
  if (input == null) return null;
  const { text, origin } = stripSpaces(String(input));
  if (text === '') return null;

  let i = 0;

  /** Позиція у вихідному рядку для повідомлення про помилку. */
  const at = (k) => (k < origin.length ? origin[k] : input.length);
  const fail = (message, k = i) => {
    throw new ParseError(message, at(k));
  };
  const peek = () => text[i];

  function parseNumber() {
    const start = i;
    let intPart = '';
    while (isDigit(peek())) intPart += text[i++];

    let fracPart = '';
    if ((peek() === '.' || peek() === ',') && isDigit(text[i + 1])) {
      i++;
      while (isDigit(peek())) fracPart += text[i++];
    }

    if (intPart === '' && fracPart === '') fail('Очікувалось число', start);

    const hryvnias = intPart === '' ? 0 : Number(intPart);
    const kopiykas = Number(fracPart.slice(0, 2).padEnd(2, '0') || '0');
    return hryvnias * 100 + kopiykas;
  }

  function parsePrimary() {
    if (peek() === '(') {
      i++;
      const value = parseExpr();
      if (peek() !== ')') fail('Не закрита дужка');
      i++;
      return value;
    }
    if (isDigit(peek()) || ((peek() === '.' || peek() === ',') && isDigit(text[i + 1]))) {
      return parseNumber();
    }
    fail('Очікувалось число');
  }

  function parseFactor() {
    if (peek() === '-') {
      i++;
      return -parseFactor();
    }
    if (peek() === '+') {
      i++;
      return parseFactor();
    }
    return parsePrimary();
  }

  function parseTerm() {
    let left = parseFactor();
    for (;;) {
      const op = peek();
      if (op === '*' || op === '×') {
        i++;
        // копійки × копійки дає копійки², тому ділимо на 100
        left = roundHalfAwayFromZero((left * parseFactor()) / 100);
      } else if (op === '/' || op === '÷') {
        const opAt = i;
        i++;
        const right = parseFactor();
        if (right === 0) fail('Ділення на нуль', opAt);
        left = roundHalfAwayFromZero((left * 100) / right);
      } else {
        return left;
      }
    }
  }

  function parseExpr() {
    let left = parseTerm();
    for (;;) {
      const op = peek();
      if (op === '+') {
        i++;
        left += parseTerm();
      } else if (op === '-') {
        i++;
        left -= parseTerm();
      } else {
        return left;
      }
    }
  }

  const value = parseExpr();
  if (i < text.length) fail('Зайвий символ');
  return value;
}

/**
 * Номінали в обігу, у копійках, від більшого до меншого.
 * Монет 1 і 5 копійок в Україні в обігу немає з 2019 року.
 */
export const DENOMINATIONS = [
  100000, 50000, 20000, 10000, 5000, 2000, 1000, 500, 200, 100, // 1000 ₴ … 1 ₴
  50, 10, // 50 к, 10 к
];

/**
 * @typedef {{ denom: number, count: number }} DenominationRow
 * @typedef {{ rounded: number, wasRounded: boolean, breakdown: DenominationRow[] }} ChangeResult
 */

/**
 * Розкладає решту на купюри й монети, мінімізуючи їх кількість.
 *
 * Готівкові розрахунки в Україні заокруглюються до найближчих 10 копійок,
 * тому решта спершу заокруглюється, і лише потім розкладається.
 *
 * @param {number} change решта в копійках
 * @returns {ChangeResult}
 */
export function makeChange(change) {
  const rounded = roundHalfAwayFromZero(change / 10) * 10;
  const breakdown = [];

  let rest = rounded;
  for (const denom of DENOMINATIONS) {
    const count = Math.floor(rest / denom);
    if (count > 0) {
      breakdown.push({ denom, count });
      rest -= denom * count;
    }
  }

  return { rounded, wasRounded: rounded !== change, breakdown };
}

/**
 * 21000 → "210 ₴", 5050 → "50,50 ₴", 868000 → "8 680 ₴".
 * Роздільник тисяч — пробіл, як у звітах бота (`fmt()` у shifts.py).
 *
 * @param {number} kopiykas
 * @returns {string}
 */
export function formatUah(kopiykas) {
  const sign = kopiykas < 0 ? '-' : '';
  const abs = Math.abs(kopiykas);
  const hryvnias = Math.floor(abs / 100);
  const rest = abs % 100;

  const whole = String(hryvnias).replace(/\B(?=(\d{3})+(?!\d))/g, ' ');
  const fraction = rest === 0 ? '' : `,${String(rest).padStart(2, '0')}`;

  return `${sign}${whole}${fraction} ₴`;
}

// Інлайнові обробники в index.html викликають функції через глобальний обʼєкт.
if (typeof window !== 'undefined') {
  window.ChangeCalc = { parseExpression, makeChange, formatUah, ParseError, DENOMINATIONS };
}
