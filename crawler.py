import re
import httpx
from bs4 import BeautifulSoup
import whois
import google.generativeai as genai
from urllib.parse import urlparse

class SovereignCrawler:
    def __init__(self, gemini_api_key: str = None):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        }
        if gemini_api_key:
            genai.configure(api_key=gemini_api_key)

    @staticmethod
    def extract_clean_domain(url_or_domain: str) -> str:
        """استخراج وتنظيف الدومين الحقيقي بدون بروتوكولات أو بادئات"""
        if not url_or_domain:
            return ""
        parsed = urlparse(url_or_domain if "://" in url_or_domain else f"http://{url_or_domain}")
        domain = parsed.netloc or parsed.path
        domain = domain.lower().replace("www.", "").strip("/")
        return domain

    async def crawl_company_website(self, domain: str) -> dict:
        clean_domain = self.extract_clean_domain(domain)
        result = {
            "owner_name": "غير محدد",
            "extracted_domain": clean_domain,
            "source": "None"
        }
        
        if not clean_domain:
            return result

        clean_url = f"https://{clean_domain}"
        target_paths = ["", "/about", "/about-us", "/team", "/leadership", "/contact"]
        
        combined_text = ""
        async with httpx.AsyncClient(headers=self.headers, timeout=8.0, follow_redirects=True, verify=False) as client:
            for path in target_paths:
                target_url = clean_url.rstrip("/") + path
                try:
                    response = await client.get(target_url)
                    if response.status_code == 200:
                        soup = BeautifulSoup(response.text, 'html.parser')
                        for script in soup(["script", "style", "nav", "footer"]):
                            script.extract()
                        combined_text += f"\n--- Path: {path} ---\n" + soup.get_text()[:2500]
                except Exception:
                    continue

        if combined_text:
            try:
                model = genai.GenerativeModel('gemini-1.5-flash')
                prompt = f"""
                Analyze the following website text extracted from a company's pages.
                Find the full name of the CEO, Founder, Owner, Managing Director, or General Manager.
                Return ONLY the full name. If you cannot find any decision maker with high certainty, return "غير محدد".
                
                Text content:
                {combined_text[:8000]}
                """
                response = model.generate_content(prompt)
                extracted_name = response.text.strip()
                if extracted_name and extracted_name != "غير محدد" and len(extracted_name.split()) >= 2:
                    result["owner_name"] = extracted_name
                    result["source"] = "Gemini AI Semantic Search"
                    return result
            except Exception as e:
                print(f"LLM Error: {e}")

        return result

    @staticmethod
    def generate_permutations(owner_name: str, domain: str) -> list:
        clean_domain = SovereignCrawler.extract_clean_domain(domain)
        permutations = []
        
        if owner_name and owner_name != "غير محدد":
            parts = owner_name.lower().split()
            if len(parts) >= 2:
                first, last = parts[0], parts[-1]
                permutations.extend([
                    f"{first}.{last}@{clean_domain}",
                    f"{first}{last}@{clean_domain}",
                    f"{first[0]}{last}@{clean_domain}",
                    f"{first}@{clean_domain}",
                    f"{last}.{first}@{clean_domain}"
                ])
        
        permutations.extend([
            f"info@{clean_domain}",
            f"contact@{clean_domain}",
            f"sales@{clean_domain}",
            f"management@{clean_domain}",
            f"enquiries@{clean_domain}"
        ])
        
        return list(dict.fromkeys(permutations))
        
