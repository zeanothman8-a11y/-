import re
import httpx
from bs4 import BeautifulSoup
from urllib.parse import urlparse
import google.generativeai as genai

class SovereignCrawler:
    def __init__(self, gemini_api_key: str = None, serpapi_key: str = None):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        }
        self.gemini_api_key = gemini_api_key
        self.serpapi_key = serpapi_key
        if gemini_api_key:
            genai.configure(api_key=gemini_api_key)

    @staticmethod
    def sanitize_company_name(company_name: str) -> str:
        clean = re.sub(r'[^\w\s]', '', company_name)
        stopwords = ['ltd', 'limited', 'llc', 'inc', 'co', 'company', 'group', 'logistics', 'transport', 'shipping', 'services', 'international']
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

    @staticmethod
    def is_spam_or_invalid_domain(domain: str) -> bool:
        if not domain or len(domain) > 45 or len(domain.split('.')) > 3:
            return True
        spam_keywords = ["casino", "bet", "xxx", "porn", "slot", "game", "shop"]
        return any(kw in domain.lower() for kw in spam_keywords)

    def search_via_serpapi(self, query: str) -> list:
        if not self.serpapi_key:
            return []
        url = "https://serpapi.com/search"
        params = {"engine": "google", "q": query, "api_key": self.serpapi_key, "num": 5}
        try:
            response = httpx.get(url, params=params, timeout=10.0)
            if response.status_code == 200:
                return response.json().get("organic_results", [])
        except Exception as e:
            print(f"SerpAPI Error: {e}")
        return []

    def find_real_domain_via_ct(self, company_name: str) -> str:
        compact_name, hyphen_name = self.sanitize_company_name(company_name)
        if not compact_name or len(compact_name) > 30:
            return ""
        url = f"https://crt.sh/?q=%{compact_name}%&output=json"
        try:
            response = httpx.get(url, headers=self.headers, timeout=8.0)
            if response.status_code == 200:
                data = response.json()
                ignored_keywords = ["google", "facebook", "apple", "microsoft", "amazon", "github", "cloudflare"]
                for entry in data:
                    name_value = entry.get("name_value", "").lower()
                    for d in name_value.split("\n"):
                        d = d.strip().replace("*.", "")
                        if d and not any(ign in d for ign in ignored_keywords) and len(d.split('.')) == 2:
                            if (compact_name in d or hyphen_name in d.replace("-", "")) and not self.is_spam_or_invalid_domain(d):
                                return d
        except Exception:
            pass
        return ""

    def find_decision_maker_and_registry(self, company_name: str, city: str) -> dict:
        result = {"executive_name": "غير محدد", "linkedin_profile": "", "found_in_dorks": False, "source_type": "Direct"}
        
        if "uk" in city.lower() or "london" in city.lower():
            registry_query = f'site:find-and-update.company-information.service.gov.uk "{company_name}" Director OR CEO'
            results = self.search_via_serpapi(registry_query)
            if results:
                result["found_in_dorks"] = True
                result["source_type"] = "Companies House UK"
        
        query = f'site:linkedin.com/in/ ("CEO" OR "Founder" OR "Managing Director" OR "Director" OR "Head of Logistics") "{company_name}"'
        results = self.search_via_serpapi(query)
        if not results:
            query_pdf = f'"{company_name}" filetype:pdf ("CEO" OR "Director" OR "Logistics")'
            results = self.search_via_serpapi(query_pdf)
            if results:
                result["found_in_dorks"] = True

        if results:
            for res in results:
                link = res.get("link", "")
                if "linkedin.com/in/" in link:
                    result["linkedin_profile"] = link
                    slug = link.split("linkedin.com/in/")[-1].split("/")[0]
                    name_parts = [w.capitalize() for w in slug.split('-') if not w.isdigit() and len(w) > 1 and w not in ['ceo', 'founder', 'owner', 'director', 'logistics', 'transport']]
                    if len(name_parts) >= 2:
                        result["executive_name"] = " ".join(name_parts[:2])
                        break
        return result

    def scrape_onsite_emails(self, domain: str) -> list:
        found_emails = set()
        paths = ["", "/contact", "/contact-us", "/about", "/about-us", "/team"]
        email_regex = r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+'
        dead_emails = ["info@", "contact@", "sales@", "support@", "enquiries@", "admin@"]

        for path in paths:
            url = f"https://{domain}{path}"
            try:
                res = httpx.get(url, headers=self.headers, timeout=5.0, follow_redirects=True)
                if res.status_code == 200:
                    for em in re.findall(email_regex, res.text):
                        em_lower = em.lower()
                        if domain in em_lower and not any(dead in em_lower for dead in dead_emails) and not any(ext in em_lower for ext in ['.png', '.jpg', '.gif']):
                            found_emails.add(em_lower)
            except Exception:
                continue
        return list(found_emails)

    async def crawl_company_website(self, company_name: str, city: str) -> dict:
        real_domain = self.find_real_domain_via_ct(company_name)
        if not real_domain or self.is_spam_or_invalid_domain(real_domain):
            compact, _ = self.sanitize_company_name(company_name)
            tld = ".co.uk" if "uk" in city.lower() or "london" in city.lower() else ".com"
            real_domain = f"{compact}{tld}" if len(compact) <= 25 else ""

        registry_data = self.find_decision_maker_and_registry(company_name, city)
        onsite_emails = self.scrape_onsite_emails(real_domain) if real_domain else []

        source_parts = [registry_data["source_type"]]
        if real_domain: source_parts.append("CT Logs")
        if onsite_emails: source_parts.append("Operational Scrape")

        return {
            "owner_name": registry_data["executive_name"],
            "extracted_domain": real_domain,
            "linkedin_profile": registry_data["linkedin_profile"],
            "found_in_dorks": registry_data["found_in_dorks"],
            "onsite_emails": onsite_emails,
            "source": " + ".join(source_parts)
        }

    @staticmethod
    def generate_permutations(owner_name: str, domain: str) -> list:
        clean_domain = SovereignCrawler.extract_clean_domain(domain)
        permutations = []
        
        # 1. إيميلات الأقسام التشغيلية الحية التي تقرأ وتتابع (بدون info و contact)
        permutations.extend([
            f"operations@{clean_domain}",
            f"logistics@{clean_domain}",
            f"fleet@{clean_domain}",
            f"dispatch@{clean_domain}",
            f"transport@{clean_domain}"
        ])

        # 2. إيميلات صاحب القرار إن وجد
        if owner_name and owner_name != "غير محدد":
            parts = owner_name.lower().split()
            if len(parts) >= 2:
                first, last = parts[0], parts[-1]
                permutations.insert(0, f"{first}.{last}@{clean_domain}")
                permutations.insert(1, f"{first}{last}@{clean_domain}")
                permutations.insert(2, f"{first}@{clean_domain}")

        return list(dict.fromkeys(permutations))
                                 
