"""E2E-перевірка вкладки «Решта» у справжньому браузері.

Запуск: python tests/e2e_change.py [base_url]
"""

import sys

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


def fill(page, due, paid):
    page.fill("#change-due", due)
    page.fill("#change-paid", paid)
    # oninput спрацьовує на fill; даємо кадр на перемальовку
    page.wait_for_timeout(50)


with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page()
    page.on("console", lambda m: console_errors.append(m.text) if m.type == "error" else None)
    page.on("pageerror", lambda e: console_errors.append(str(e)))

    page.goto(BASE, wait_until="networkidle")

    print("\n[вкладка]")
    page.click("text=💱 Решта")
    check("панель активна", page.is_visible("#change"), True)
    check("модуль завантажено", page.evaluate("typeof window.ChangeCalc"), "object")

    print("\n[решта з решти]")
    fill(page, "50+100", "200")
    check("підсумок до сплати", page.inner_text("#change-due-preview"), "= 150 ₴")
    check("підсумок дали", page.inner_text("#change-paid-preview"), "= 200 ₴")
    check("підпис", page.text_content("#change-result .cashcount-total-label"), "Решта")
    check("сума", page.inner_text("#change-result .cashcount-total-amount"), "50 ₴")
    check("розбивка", page.inner_text("#change-result .change-breakdown").split(), ["50₴", "×", "1"])

    print("\n[множення: три години по 70]")
    fill(page, "3*70", "200")
    check("підсумок до сплати", page.inner_text("#change-due-preview"), "= 210 ₴")
    check("підпис", page.text_content("#change-result .cashcount-total-label"), "Не вистачає")
    check("нестача", page.inner_text("#change-result .cashcount-total-amount"), "10 ₴")
    check("розбивки немає", page.locator("#change-result .change-breakdown").count(), 0)

    print("\n[рівно]")
    fill(page, "100", "100")
    check("сума", page.inner_text("#change-result .cashcount-total-amount"), "0 ₴")
    check("напис", page.inner_text("#change-result .change-exact"), "Без решти ✅")

    print("\n[складна розбивка: 163 ₴]")
    fill(page, "137", "300")
    check("сума", page.inner_text("#change-result .cashcount-total-amount"), "163 ₴")
    check(
        "купюри",
        [t.strip() for t in page.locator("#change-result .change-denom").all_inner_texts()],
        ["100₴\n× 1", "50₴\n× 1", "10₴\n× 1", "2₴\n× 1", "1₴\n× 1"],
    )

    print("\n[хибний вираз]")
    fill(page, "50+", "200")
    check("поле підсвічене", "input-error" in (page.get_attribute("#change-due", "class") or ""), True)
    check("помилка червона", "is-error" in (page.get_attribute("#change-due-preview", "class") or ""), True)
    check("результат прихований", page.inner_html("#change-result").strip(), "")

    print("\n[порожній ввід]")
    fill(page, "", "")
    check("підсумок порожній", page.inner_text("#change-due-preview"), "")
    check("поле не червоне", "input-error" in (page.get_attribute("#change-due", "class") or ""), False)
    check("результат порожній", page.inner_html("#change-result").strip(), "")

    print("\n[очищення]")
    fill(page, "50+100", "500")
    page.click("#change button.btn-secondary")
    page.wait_for_timeout(50)
    check("поле до сплати", page.input_value("#change-due"), "")
    check("поле дали", page.input_value("#change-paid"), "")
    check("результат прибрано", page.inner_html("#change-result").strip(), "")

    print("\n[інші вкладки не зламані]")
    page.click("text=💵 Рахунок каси")
    check("рахунок каси видимий", page.is_visible("#cashcount"), True)
    page.click("text=🧮 Калькулятор годин")
    check("калькулятор видимий", page.is_visible("#calculator"), True)
    page.click("text=💼 Управління касою")
    check("управління касою видиме", page.is_visible("#report"), True)

    page.click("text=💱 Решта")
    fill(page, "2*80+50", "500")
    page.screenshot(path="tests/screenshot-change.png", full_page=True)

    browser.close()

print("\n[консоль браузера]")
if console_errors:
    print("  FAIL помилки в консолі:")
    for e in console_errors:
        print("   ", e)
    failures.append("console")
else:
    print("  ok   помилок немає")

print()
if failures:
    print(f"ПРОВАЛЕНО: {len(failures)} — {', '.join(failures)}")
    sys.exit(1)
print("Усі перевірки пройдено.")
