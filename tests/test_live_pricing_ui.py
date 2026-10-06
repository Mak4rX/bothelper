import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1280, "height": 950})
        await page.goto("http://127.0.0.1:8000")
        await page.wait_for_timeout(1000)

        # 1. Click Калькулятор
        tabs = await page.query_selector_all(".main-tab")
        # 0: cash, 1: reviews, 2: promotions, 3: calculator
        await tabs[3].click()
        await page.wait_for_timeout(1500)

        await page.screenshot(path="tests/screenshot_live_pricing_default.png", full_page=True)
        print("Captured default live pricing screenshot")

        # 2. Click morning preset
        await page.click("#sim-preset-morning")
        await page.wait_for_timeout(1000)
        await page.screenshot(path="tests/screenshot_live_pricing_morning.png", full_page=True)
        print("Captured morning preset screenshot")

        # 3. Click night preset
        await page.click("#sim-preset-night")
        await page.wait_for_timeout(1000)
        await page.screenshot(path="tests/screenshot_live_pricing_night.png", full_page=True)
        print("Captured night preset screenshot")

        # 4. Click 'Відкрити в калькуляторі' on Gamer Zone card
        jump_btns = await page.query_selector_all(".live-zone-footer button")
        if jump_btns:
            await jump_btns[0].click()
            await page.wait_for_timeout(1000)
            await page.screenshot(path="tests/screenshot_calc_jump.png")
            print("Captured jump to calculator screenshot")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
