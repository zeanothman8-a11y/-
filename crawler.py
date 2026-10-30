import re
import httpx
from bs4 import BeautifulSoup
import whois
import google.generativeai as genai

class SovereignCrawler:
    def __init__(self, gemini_api_key: str = None):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        }
        if gemini_api_key:
            genai.configure(api_key=gemini_api_key)

    async def crawl_company_website(self, domain: str) -> dict:
        result = {
            "owner_name": "غير محدد",
            "extracted_domain": domain,
            "source": "None"
        }
        
        if not domain:
            return result

        clean_url = f"https://{domain}" if not domain.startswith("http") else domain
        target_paths = ["", "/about", "/about-us", "/team", "/leadership", "/contact", "/management"]
        
        combined_text = ""
        async with httpx.AsyncClient(headers=self.headers, timeout=10.0, follow_redirects=True) as client:
            for path in target_paths:
                target_url = clean_url.rstrip("/") + path
                try:
                    response = await client.get(target_url)
                    if response.status_code == 200:
                        soup = BeautifulSoup(response.text, 'html.parser')
                        for script in soup(["script", "style", "nav", "footer"]):
                            script.extract()
                        combined_text += f"\n--- Path: {path} ---\n" + soup.get_text()[:3000]
                except Exception:
                    continue

        # 1. استخراج صاحب القرار عبر نموذج Gemini
        if combined_text:
            try:
                model = genai.GenerativeModel('gemini-1.5-flash')
                prompt = f"""
                Analyze the following website text extracted from a company's pages (About, Team, Leadership).
                Find the full name of the CEO, Founder, Owner, Managing Director, or General Manager.
                Return ONLY the full name. If you cannot find any decision maker with high certainty, return "غير محدد".
                
                Text content:
                {combined_text[:10000]}
                """
                response = model.generate_content(prompt)
                extracted_name = response.text.strip()
                if extracted_name and extracted_name != "غير محدد" and len(extracted_name.split()) >= 2:
                    result["owner_name"] = extracted_name
                    result["source"] = "Gemini Semantic LLM Extraction"
                    return result
            except Exception as e:
                print(f"LLM Extraction Error: {e}")

        # 2. الطريقة الاحتياطية الأولى: فحص سجلات WHOIS
        try:
            w = whois.whois(domain)
            if w.name:
                owner = w.name if isinstance(w.name, str) else w.name[0]
                if len(owner.split()) >= 2:
                    result["owner_name"] = owner
                    result["source"] = "WHOIS Database Registry"
                    return result
        except Exception:
            pass

        return result

    @staticmethod
    def generate_permutations(owner_name: str, domain: str) -> list:
        clean_domain = domain.lower().replace("https://", "").replace("http://", "").replace("www.", "").strip("/")
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
            f"ceo@{clean_domain}",
            f"director@{clean_domain}",
            f"management@{clean_domain}",
            f"info@{clean_domain}",
            f"contact@{clean_domain}",
            f"sales@{clean_domain}"
        ])
        
        return list(dict.fromkeys(permutations))
                    
