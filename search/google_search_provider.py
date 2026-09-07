from playwright.sync_api import sync_playwright

from models.search_result import SearchResult
from search.search_provider import SearchProvider


class GoogleSearchProvider(SearchProvider):

    def search(self, query: str) -> list[SearchResult]:

        with sync_playwright() as playwright:

            browser = playwright.chromium.launch(
                headless=False
            )

            page = browser.new_page()

            print("Abriendo Google...")

            page.goto(
                "https://www.google.com",
                wait_until="domcontentloaded"
            )

            print("Google cargado.")

            search_box = page.locator("textarea[name='q']")

            print("Buscando campo de búsqueda...")

            search_box.wait_for(
                state="visible",
                timeout=10000
            )

            print("Campo encontrado.")

            search_box.fill(query)

            print(f"Consulta escrita: {query}")

            search_box.press("Enter")

            print("Enter presionado.")

            page.wait_for_load_state(
                "domcontentloaded"
            )

            print("Página de resultados cargada.")

            page.wait_for_timeout(5000)

            input("Presiona ENTER para cerrar el navegador...")

            browser.close()

        return []