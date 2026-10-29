import asyncio
import random
from playwright.async_api import async_playwright

class SovereignScraper:
    def __init__(self, city: str, keyword: str, max_results: int = 20):
        self.city = city
        self.keyword = keyword
        self.max_results = max_results
        # قائمة تغيير الهويات (User-Agents) لتجنب الحظر البصري من المنصات
        self.user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2.1 Safari/605.1.15",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
        ]

    async def scrape_maps(self):
        scraped_data = []
        search_query = f"{self.keyword} in {self.city}"
        target_url = f"https://www.google.com/maps/search/{search_query.replace(' ', '+')}"

        async with async_playwright() as p:
            # تشغيل المتصفح بوضع مخفي مع كسر كشف الأتمتة
            browser = await p.chromium.launch(
                headless=True,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--disable-infobars",
                    "--disable-dev-shm-usage",
                    "--disable-gpu"
                ]
            )
            
            context = await browser.new_context(
                user_agent=random.choice(self.user_agents),
                viewport={"width": 1920, "height": 1080},
                locale="en-US"
            )
            
            # حقن أكواد جافاسكريبت لإخفاء ملامح الروبوت تماماً عن المواقع المستهدفة
            await context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
            """)

            page = await context.new_page()
            
            try:
                print(f"[*] جاري الاتصال بالهدف عبر خريطة جوجل: {search_query}")
                await page.goto(target_url, timeout=60000)
                await page.wait_for_timeout(4000)

                scroll_selector = 'div[role="feed"]'
                try:
                    await page.wait_for_selector(scroll_selector, timeout=15000)
                except Exception:
                    print("[!] تحذير: لم يتم العثور على حقل التمرير الرئيسي، محاولة الاستخراج المباشر...")

                collected_count = 0
                seen_hrefs = set()

                # حلقة التمرير الذكي (Infinite Scroll Simulation) لتفريغ البيانات
                for step in range(12):
                    if collected_count >= self.max_results:
                        break

                    cards = await page.query_selector_all('a[href*="/maps/place/"]')
                    
                    for card in cards:
                        if collected_count >= self.max_results:
                            break
                            
                        href = await card.get_attribute("href")
                        if href in seen_hrefs:
                            continue
                        seen_hrefs.add(href)

                        aria_label = await card.get_attribute("aria-label")
                        company_name = aria_label if aria_label else await card.inner_text()
                        company_name = company_name.split('\n')[0].strip()

                        if company_name and len(company_name) > 2:
                            scraped_data.append({
                                "company_name": company_name,
                                "maps_link": href,
                                "city": self.city
                            })
                            collected_count += 1

                    # تمرير الصفحة للأسفل ببطء بشري محاكى
                    if await page.query_selector(scroll_selector):
                        await page.eval_on_selector(scroll_selector, "el => el.scrollBy(0, 1500)")
                        await page.wait_for_timeout(random.randint(2000, 3500))
                    else:
                        break

            except Exception as e:
                print(f"[X] حدث خطأ أثناء السحب: {str(e)}")
            finally:
                await browser.close()

        return scraped_data
          
