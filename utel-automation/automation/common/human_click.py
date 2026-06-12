"""HumanClickSimulator — simula clicks con movimiento realista de mouse."""

from playwright.async_api import Page


async def human_click_point(page: Page, x: float, y: float) -> None:
    """Mueve el mouse como humano y hace click en (x, y)."""
    await page.mouse.move(x - 18, y - 8, steps=8)
    await page.wait_for_timeout(180)
    await page.mouse.move(x, y, steps=6)
    await page.wait_for_timeout(120)
    await page.mouse.down()
    await page.wait_for_timeout(90)
    await page.mouse.up()
