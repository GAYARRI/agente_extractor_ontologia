from playwright.sync_api import sync_playwright
from urllib.parse import urljoin


class PlaywrightCrawler:

    def __init__(self, max_pages=100):
        self.max_pages = max_pages

    def crawl(self, seed_url):

        pages = []
        visited = set()
        queue = [seed_url]

        with sync_playwright() as p:
            
            browser = p.chromium.launch(
            channel="chrome",
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage"
            ]
        )



            page = browser.new_page()

            while queue and len(pages) < self.max_pages:

                url = queue.pop(0)

                if url in visited:
                    continue

                visited.add(url)

                try:

                    print("[Playwright] Crawling:", url)

                    page.goto(url, timeout=60000)
                    page.wait_for_timeout(2000)

                    html = page.content()

                    pages.append({
                        "url": url,
                        "html": html,
                        "text": html
                    })

                    # descubrir links internos
                    links = page.eval_on_selector_all(
                        "a[href]",
                        "els => els.map(e => e.href)"
                    )

                    for link in links:

                        if seed_url in link and link not in visited:
                            queue.append(link)

                except Exception as e:

                    print("[WARN] Playwright error:", e)

            browser.close()

        return pages