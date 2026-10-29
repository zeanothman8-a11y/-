import re
import httpx
from bs4 import BeautifulSoup
import whois
from urllib.parse import urlparse

class SovereignCrawler:
    def __init__(self):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        }

    # استخراج الموقع الإلكتروني والدومين الحقيقي للشركة من رابط الخرائط أو البحث
    def extract_domain_from_maps(self, maps_link: str) -> str:
        # محاولة استخلاص الدومين أو توليده افتراضياً بناءً على اسم الشركة
        return ""

    # المحرك الثاني: الزحف الداخلي (Internal Crawler) والبحث عن أصحاب القرار
    async def crawl_company_website(self, domain: str) -> dict:
        result = {
            "owner_name": "غير محدد",
            "extracted_domain": domain,
            "source": "None"
        }
        
        if not domain:
            return result

        clean_url = f"https://{domain}" if not domain.startswith("http") else domain
        
        # صفحات المستهدفين داخل أي موقع تجاري
        target_paths = ["", "/about", "/about-us", "/team", "/leadership", "/contact", "/management"]
        
        async with httpx.AsyncClient(headers=self.headers, timeout=10.0, follow_redirects=True) as client:
            for path in target_paths:
                target_url = clean_url.rstrip("/") + path
                try:
                    response = await client.get(target_url)
                    if response.status_code == 200:
                        soup = BeautifulSoup(response.text, 'html.parser')
                        
                        # بحث ذكي عبر الكلمات المفتاحية عن المناصب الإدارية العليا
                        text_content = soup.get_text()
                        ceo_pattern = r"(?:CEO|Founder|Owner|Managing Director|Director|المدير التنفيذي|المؤسس)[:\s\-]+([A-Z][a-z]+\s[A-Z][a-z]+)"
                        match = re.search(ceo_pattern, text_content)
                        
                        if match:
                            result["owner_name"] = match.group(1)
                            result["source"] = f"Internal Crawler ({path or 'Home'})"
                            return result
                except Exception:
                    continue

        # الطريقة البديلة المعقدة: فحص سجلات WHOIS للملكية الحرة (تفيد جداً في الشركات الصغيرة)
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

    # المحرك الثالث: مصفوفة توليد الإيميلات الاحترافية العميقة
    def generate_permutations(self, owner_name: str, domain: str) -> list:
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
                    f"{first}@{last}@{clean_domain}"
                ])
        
        # الاحتمالات السيادية الافتراضية للشركات
        permutations.extend([
            f"ceo@{clean_domain}",
            f"info@{clean_domain}",
            f"contact@{clean_domain}",
            f"operations@{clean_domain}",
            f"sales@{clean_domain}"
        ])
        
        return list(dict.fromkeys(permutations)) # إزالة التكرار مع الحفاظ على الترتيب
      
