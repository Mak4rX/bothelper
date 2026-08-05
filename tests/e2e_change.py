"""E2E-перевірка локальної каси та видачі решти.

Запуск: python tests/e2e_change.py [base_url]
"""

import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

from playwright.sync_api import sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8123"
failures = []
console_errors = []


def check(label, actual, expected):
    if actual == expected:
        print(f"  ok   {label}: {actual!r}")
    else:
        print(f"  FAIL {label}: очікувалось {expected!r}, отримано {actual!r}")
        failures.append(label)


def add_received(page, denom, times=1):
    button = f'.received-denom-tile[data-value="{denom}"]'
    for _ in range(times):
        page.click(button)
    page.wait_for_timeout(30)


with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page()
    page.on("console", lambda m: console_errors.append(m.text) if m.type == "error" else None)
    page.on("pageerror", lambda e: console_errors.append(str(e)))
    page.goto(BASE, wait_until="networkidle")

    print("\n[локальна каса]")
    page.click("text=💵 Рахунок каси")
    page.fill('#cashcount .denom-input[data-value="50"]', "2")
    page.fill('#cashcount .denom-input[data-value="20"]', "2")
    page.fill('#cashcount .denom-input[data-value="10"]', "1")
    page.reload(wait_until="networkidle")
    page.click("text=💵 Рахунок каси")
    check("памʼять 50 грн", page.input_value('#cashcount .denom-input[data-value="50"]'), "2")
    check("памʼять 20 грн", page.input_value('#cashcount .denom-input[data-value="20"]'), "2")
    check("сума каси", page.inner_text("#cashcount-total"), "150 грн")

    print("\n[розрахунок і підтвердження]")
    page.click("text=💱 Решта")
    check("панель активна", page.is_visible("#change"), True)
    check("модуль каси", page.evaluate("typeof window.CashRegister"), "object")
    page.fill("#change-due", "150")
    add_received(page, "200")
    check("кнопка додає 200 грн", page.input_value('.received-denom-input[data-value="200"]'), "1")
    check("лічильник на плитці", page.inner_text('.received-denom-tile[data-value="200"] .received-denom-count'), "× 1")
    check("підсумок дали", page.inner_text("#change-paid-preview"), "= 200 ₴")
    check("сума решти", page.inner_text("#change-result .cashcount-total-amount"), "50 ₴")
    check("розбивка", page.inner_text("#change-result .change-breakdown").split(), ["50₴", "×", "1"])
    check("підтвердження доступне", page.is_visible("#confirm-sale"), True)
    page.click("#confirm-sale")
    check("операцію проведено", "Продаж підтверджено" in page.inner_text("#change-result"), True)

    page.click("text=💵 Рахунок каси")
    check("отримано 200 грн", page.input_value('#cashcount .denom-input[data-value="200"]'), "1")
    check("видано одну 50 грн", page.input_value('#cashcount .denom-input[data-value="50"]'), "1")
    check("нова сума каси", page.inner_text("#cashcount-total"), "300 грн")

    print("\n[неможлива точна решта]")
    page.click("text=💱 Решта")
    page.fill("#change-due", "199,70")
    add_received(page, "200", 2)
    check("повторне натискання додає дві купюри", page.input_value('.received-denom-input[data-value="200"]'), "2")
    check("лічильник показує дві купюри", page.inner_text('.received-denom-tile[data-value="200"] .received-denom-count'), "× 2")
    check("підсумок повторних натискань", page.inner_text("#change-paid-preview"), "= 400 ₴")
    check("попередження", "точно видати неможливо" in page.inner_text("#change-result"), True)
    check("кнопка прихована", page.is_visible("#confirm-sale"), False)

    print("\n[хибний вираз]")
    page.fill("#change-due", "50+")
    check("поле підсвічене", "input-error" in (page.get_attribute("#change-due", "class") or ""), True)
    check("результат прихований", page.inner_html("#change-result").strip(), "")

    page.screenshot(path="tests/screenshot-change.png", full_page=True)
    browser.close()

print("\n[консоль браузера]")
if console_errors:
    print("  FAIL помилки в консолі:")
    for error in console_errors:
        print("   ", error)
    failures.append("console")
else:
    print("  ok   помилок немає")

print()
if failures:
    print(f"ПРОВАЛЕНО: {len(failures)} — {', '.join(failures)}")
    sys.exit(1)
print("Усі перевірки пройдено.")
