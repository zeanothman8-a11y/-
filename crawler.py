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
        """
        فلترة النطاقات المشبوهة، الكازينوهات، أو الدومينات الطويلة جداً التي تسبب الارتداد (Bounce)
        """
        if not domain or len(domain) > 45 or len(domain.split('.')) > 3:
            return True
        spam_keywords = ["casino", "bet", "xxx", "porn", "slot", "game", "shop"]
        return any(kw in domain.lower() for kw in spam_keywords)

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
                    domains = name_value.split("\n")
                    for d in domains:
                        d = d.strip().replace("*.", "")
                        if d and not any(ign in d for ign in ignored_keywords) and len(d.split('.')) == 2:
                            if (compact_name in d or hyphen_name in d.replace("-", "")) and not self.is_spam_or_invalid_domain(d):
                                return d
        except Exception:
            pass
        return ""

    def find_decision_maker_social(self, company_name: str) -> dict:
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

    def scrape_onsite_emails(self, domain: str) -> list:
        """
        الزحف العميق داخل صفحات الموقع الرسمي (/contact, /about, /team) لاستخراج إيميلات حقيقية
        """
        found_emails = set()
        paths = ["", "/contact", "/contact-us", "/about", "/about-us", "/team"]
        email_regex = r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+'

        for path in paths:
            url = f"https://{domain}{path}"
            try:
                res = httpx.get(url, headers=self.headers, timeout=5.0, follow_redirects=True)
                if res.status_code == 200:
                    emails = re.findall(email_regex, res.text)
                    for em in emails:
                        em_lower = em.lower()
                        if domain in em_lower and not any(ext in em_lower for ext in ['.png', '.jpg', '.gif', 'example', 'domain']):
                            found_emails.add(em_lower)
            except Exception:
                continue
        return list(found_emails)

    def check_archive_dorks(self, domain: str, company_name: str) -> bool:
        clean_domain = self.extract_clean_domain(domain)
        if not clean_domain:
            return False

        queries = [
            f'site:{clean_domain} filetype:pdf',
            f'site:{clean_domain} "@{clean_domain}"',
            f'"{company_name}" "@{clean_domain}"'
        ]

        for q in queries:
            search_url = f"https://html.duckduckgo.com/html/?q={httpx.URL(q).params}"
            try:
                response = httpx.get(search_url, headers=self.headers, timeout=6.0)
                if response.status_code == 200:
                    if f"@{clean_domain}" in response.text or "pdf" in response.text.lower():
                        return True
            except Exception:
                continue
        return False

    async def crawl_company_website(self, company_name: str, city: str) -> dict:
        # 1. جلب الدومين الحقيقي مع منع الدومينات الوهمية والمشبوهة
        real_domain = self.find_real_domain_via_ct(company_name)
        if not real_domain or self.is_spam_or_invalid_domain(real_domain):
            compact, hyphen = self.sanitize_company_name(company_name)
            tld = ".co.uk" if "uk" in city.lower() or "london" in city.lower() else ".com"
            candidate = f"{compact}{tld}"
            if self.is_spam_or_invalid_domain(candidate) or len(compact) > 25:
                real_domain = "" # رفض القاطع للدومينات الوهمية الطويلة
            else:
                real_domain = candidate

        # 2. البحث عن صاحب القرار عبر لينكد إن
        social_data = self.find_decision_maker_social(company_name)
        owner_name = social_data["executive_name"]
        
        # 3. الفحص الأرشيفي العميق عبر Dorks
        found_in_dorks = self.check_archive_dorks(real_domain, company_name) if real_domain else False
        
        # 4. البحث المباشر عن إيميلات في موقع الشركة
        onsite_emails = self.scrape_onsite_emails(real_domain) if real_domain else []

        source_parts = []
        if owner_name != "غير محدد":
            source_parts.append("LinkedIn Dorks")
        if real_domain:
            source_parts.append("CT Logs")
        if found_in_dorks:
            source_parts.append("Deep Archive Dorks")
        if onsite_emails:
            source_parts.append("On-site Scrape")
            
        source = " + ".join(source_parts) if source_parts else "Direct"

        return {
            "owner_name": owner_name,
            "extracted_domain": real_domain,
            "linkedin_profile": social_data.get("linkedin_profile", ""),
            "found_in_dorks": found_in_dorks,
            "onsite_emails": onsite_emails,
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
                    f"{first}{last[0]}@{clean_domain}",
                    f"{first[0]}.{last}@{clean_domain}",
                    f"{first}@{clean_domain}"
                ])
        
        permutations.extend([
            f"info@{clean_domain}",
            f"contact@{clean_domain}",
            f"sales@{clean_domain}"
        ])
        return list(dict.fromkeys(permutations))
        
