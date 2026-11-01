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
        self.gemini_api_key = gemini_api_key
        if gemini_api_key:
            genai.configure(api_key=gemini_api_key)

    @staticmethod
    def sanitize_company_name(company_name: str) -> str:
        """
        تطهير اسم الشركة وإزالة الرموز لتوليد دومين نظيف
        """
        clean = re.sub(r'[^\w\s]', '', company_name)
        stopwords = ['ltd', 'limited', 'llc', 'inc', 'co', 'company', 'group', 'logistics', 'transport', 'shipping']
        words = [w for w in clean.lower().split() if w not in stopwords]
        if not words:
            words = clean.lower().split()
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
        البحث الذكي عبر سجلات الشهادات الرقمية (crt.sh API) للتعرف على الدومين الحقيقي
        """
        compact_name, hyphen_name = self.sanitize_company_name(company_name)
        if not compact_name:
            return ""
        
        url = f"https://crt.sh/?q=%{compact_name}%&output=json"
        try:
            response = httpx.get(url, headers=self.headers, timeout=8.0)
            if response.status_code == 200:
                data = response.json()
                ignored_keywords = ["google", "facebook", "apple", "microsoft", "amazon", "github", "cloudflare"]
                
                for entry in data:
                    name_value = entry.get("name_value", "").lower()
                    domains = name_value.split("\n")
                    for d in domains:
                        d = d.strip().replace("*.", "")
                        if d and not any(ign in d for ign in ignored_keywords) and len(d.split('.')) == 2:
                            if compact_name in d or hyphen_name in d.replace("-", ""):
                                return d
        except Exception:
            pass
            
        return ""

    def find_decision_maker_social(self, company_name: str) -> dict:
        """
        بحث هندسي متقدم عبر DuckDuckGo للعثور على حساب لينكد إن الخاص بالمدير التنفيذي أو المؤسس
        """
        query = f'site:linkedin.com/in/ ("CEO" OR "Founder" OR "Managing Director" OR "Owner" OR "Director") "{company_name}"'
        search_url = f"https://html.duckduckgo.com/html/?q={httpx.URL(query).params}"
        
        result = {
            "executive_name": "غير محدد",
            "linkedin_profile": "",
            "confidence": 0
        }

        try:
            response = httpx.get(search_url, headers=self.headers, timeout=8.0)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                results = soup.select('.result__url')
                
                for res in results:
                    raw_url = res.get('href', '')
                    if "uddg=" in raw_url:
                        import urllib.parse
                        parsed_q = urllib.parse.parse_qs(urllib.parse.urlparse(raw_url).query)
                        if "uddg" in parsed_q:
                            raw_url = parsed_q["uddg"][0]
                    
                    if "linkedin.com/in/" in raw_url:
                        result["linkedin_profile"] = raw_url
                        
                        # محاولة استخراج اسم الشخص تلقائياً من رابط لينكد إن (Slug)
                        slug = raw_url.split("linkedin.com/in/")[-1].split("/")[0]
                        clean_slug = slug.split('-')
                        name_parts = [w.capitalize() for w in clean_slug if not w.isdigit() and len(w) > 1 and w not in ['ceo', 'founder', 'owner', 'director', 'logistics', 'transport']]
                        
                        if len(name_parts) >= 2:
                            result["executive_name"] = " ".join(name_parts[:2])
                        
                        result["confidence"] = 90
                        break
        except Exception as e:
            print(f"Executive Hunt Error: {e}")

        return result

    async def crawl_company_website(self, company_name: str, city: str) -> dict:
        # 1. جلب الدومين الحقيقي
        real_domain = self.find_real_domain_via_ct(company_name)
        if not real_domain:
            compact, hyphen = self.sanitize_company_name(company_name)
            tld = ".co.uk" if "uk" in city.lower() or "london" in city.lower() else ".com"
            real_domain = f"{compact}{tld}"

        # 2. البحث عن صاحب القرار عبر لينكد إن
        social_data = self.find_decision_maker_social(company_name)
        owner_name = social_data["executive_name"]
        source = "LinkedIn Dorks + CT Logs" if owner_name != "غير محدد" else "CT Logs Only"

        return {
            "owner_name": owner_name,
            "extracted_domain": real_domain,
            "linkedin_profile": social_data.get("linkedin_profile", ""),
            "source": source
        }

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
            f"sales@{clean_domain}",
            f"operations@{clean_domain}"
        ])
        return list(dict.fromkeys(permutations))
        
