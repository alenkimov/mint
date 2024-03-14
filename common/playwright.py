from contextlib import asynccontextmanager

from undetected_playwright.async_api import async_playwright, Browser, Playwright
from better_proxy import Proxy


class UndetectedPlaywrightBrowser:
    """
    - Использует undetected_playwright
    - Принимает прокси в формате URL и better-proxy.
    - Устанавливает таймаут в 10 сек по умолчанию.
    """
    proxy: Proxy | None

    def __init__(
            self,
            *,
            default_timeout: int = 10_000,
            proxy: str | Proxy = None,  # TODO Принимать в Playwright формате тоже
            **launch_kwargs
    ):
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self.proxy = Proxy.from_str(proxy) if proxy else None
        self.launch_kwargs = launch_kwargs
        self.default_timeout = default_timeout

    async def create_browser(self):
        self._playwright = await async_playwright().start()
        proxy = self.proxy.as_playwright_proxy if self.proxy else {"server": 'http://per-context'}

        # disable navigator.webdriver:true flag
        args = ["--disable-blink-features=AutomationControlled"]
        self._browser = await self._playwright.chromium.launch(proxy=proxy, args=args, **self.launch_kwargs)

    async def close_browser(self):
        await self._browser.close()
        await self._playwright.stop()

    async def __aenter__(self):
        await self.create_browser()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close_browser()

    @asynccontextmanager
    async def new_context(
            self,
            *,
            proxy: str | Proxy = None,  # TODO Принимать в Playwright формате тоже
            **context_kwargs,
    ):
        proxy = Proxy.from_str(proxy).as_playwright_proxy if proxy else None
        context = await self._browser.new_context(proxy=proxy, **context_kwargs)
        context.set_default_timeout(self.default_timeout)
        yield context
        await context.close()
