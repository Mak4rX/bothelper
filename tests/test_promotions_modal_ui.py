import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1280, "height": 950})
        await page.goto("http://127.0.0.1:8000")
        await page.wait_for_timeout(1000)

        # 1. Click '🎁 Акції' tab (3rd tab, index 2)
        tabs = await page.query_selector_all(".main-tab")
        await tabs[2].click()
        await page.wait_for_timeout(1200)

        # Capture screenshot of Promotions panel with the Today Tariffs widget
        await page.screenshot(path="tests/screenshot_promotions_today_tariffs.png", full_page=True)
        print("Captured screenshot_promotions_today_tariffs.png")

        # 2. Click 'Редагувати' button
        edit_btn = await page.query_selector("#promotions-admin-toggle")
        print("Clicking edit button...")
        await edit_btn.click()
        await page.wait_for_timeout(800)

        # Capture screenshot of Modal with Promotions List
        await page.screenshot(path="tests/screenshot_promotions_modal_list.png")
        print("Captured screenshot_promotions_modal_list.png")

        # 3. Click '➕ Додати акцію' in modal
        await page.click("#modal-tab-form")
        await page.wait_for_timeout(600)
        await page.screenshot(path="tests/screenshot_promotions_modal_form.png")
        print("Captured screenshot_promotions_modal_form.png")

        # 4. Close modal
        await page.click(".modal-close-btn")
        await page.wait_for_timeout(600)

        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
