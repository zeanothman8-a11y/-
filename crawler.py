import re
import httpx
from bs4 import BeautifulSoup
from urllib.parse import urlparse
import google.generativeai as genai

class SovereignCrawler:
    def __init__(self, gemini_api_key: str = None):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        }
        if gemini_api_key:
            genai.configure(api_key=gemini_api_key)

    @staticmethod
    def sanitize_company_name(company_name: str) -> str:
        """
        تطهير اسم الشركة وإزالة الرموز الخطيرة مثل & والمسافات الزائدة
        """
        # إزالة الرموز الخاصة
        clean = re.sub(r'[^\w\s]', '', company_name)
        # إزالة كلمات الشركات الشائعة لتوليد الدومين النظيف
        stopwords = ['ltd', 'limited', 'llc', 'inc', 'co', 'company', 'group']
        words = [w for w in clean.lower().split() if w not in stopwords]
        return "".join(words), "-".join(words)

    @staticmethod
    def extract_clean_domain(url_or_domain: str) -> str:
        if not url_or_domain:
            return ""
        parsed = urlparse(url_or_domain if "://" in url_or_domain else f"http://{url_or_domain}")
        domain = parsed.netloc or parsed.path
        return domain.lower().replace("www.", "").strip("/")

    def find_real_domain_via_ct(self, company_name: str) -> str:
        """
        البحث الذكي العالي الدقة عبر سجلات الشهادات الرقمية (crt.sh API) لتجنب الحظر
        """
        compact_name, hyphen_name = self.sanitize_company_name(company_name)
        if not compact_name:
            return ""
        
        # استعلام سجلات الـ SSL العالمية عبر HTTPS (منفذ 443 غير محظور)
        url = f"https://crt.sh/?q=%{compact_name}%&output=json"
        try:
            response = httpx.get(url, headers=self.headers, timeout=10.0)
            if response.status_code == 200:
                data = response.json()
                ignored_keywords = ["google", "facebook", "apple", "microsoft", "amazon", "github", "cloudflare"]
                
                for entry in data:
                    name_value = entry.get("name_value", "").lower()
                    # استخراج أول دومين صالح غير فرعي معقد
                    domains = name_value.split("\n")
                    for d in domains:
                        d = d.strip().replace("*.", "")
                        if d and not any(ign in d for ign in ignored_keywords) and len(d.split('.')) == 2:
                            if compact_name in d or hyphen_name in d.replace("-", ""):
                                return d
        except Exception:
            pass
            
        return ""

    async def crawl_company_website(self, company_name: str, city: str) -> dict:
        real_domain = self.find_real_domain_via_ct(company_name)
        
        result = {
            "owner_name": "غير محدد",
            "extracted_domain": real_domain,
            "source": "CT Logs (SSL Intelligence)" if real_domain else "Fallback Pattern"
        }
        
        if not real_domain:
            compact, hyphen = self.sanitize_company_name(company_name)
            tld = ".co.uk" if "uk" in city.lower() or "london" in city.lower() else ".com"
            real_domain = f"{compact}{tld}"
            result["extracted_domain"] = real_domain

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
                    f"{first}@{clean_domain}"
                ])
        
        permutations.extend([
            f"info@{clean_domain}",
            f"contact@{clean_domain}",
            f"sales@{clean_domain}"
        ])
        return list(dict.fromkeys(permutations))
        
