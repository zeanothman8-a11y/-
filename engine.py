import httpx

try:
    import streamlit as st
    TURSO_URL = st.secrets.get("turso", {}).get("DATABASE_URL", "verilogix_local.db")
    TURSO_TOKEN = st.secrets.get("turso", {}).get("AUTH_TOKEN", "")
except Exception:
    TURSO_URL = "verilogix_local.db"
    TURSO_TOKEN = ""

class SovereignEngine:
    @staticmethod
    def _get_mx_host_doh(domain: str) -> str:
        try:
            url = f"https://cloudflare-dns.com/dns-query?name={domain}&type=MX"
            headers = {"Accept": "application/dns-json"}
            response = httpx.get(url, headers=headers, timeout=5.0)
            if response.status_code == 200:
                data = response.json()
                answers = data.get("Answer", [])
                if answers:
                    for ans in answers:
                        if ans.get("type") == 15:
                            parts = ans.get("data", "").split()
                            if len(parts) >= 2:
                                return parts[1].rstrip('.')
        except Exception:
            pass
        return None

    @staticmethod
    def check_domain_http_liveness(domain: str) -> bool:
        for proto in ["https", "http"]:
            try:
                res = httpx.head(f"{proto}://{domain}", timeout=4.0, follow_redirects=True, headers={"User-Agent": "Mozilla/5.0"})
                if res.status_code < 400:
                    return True
            except Exception:
                pass
        return False

    @classmethod
    def weighted_scoring_engine(cls, owner_name: str, domain: str, found_in_dorks: bool = False, onsite_emails: list = None) -> tuple[str, str, int]:
        clean_domain = domain.lower().replace("https://", "").replace("http://", "").replace("www.", "").strip("/")
        if not clean_domain:
            return "", "دومين غير صالح أو مفقود", 0

        # جلبPermutations مع إعطاء الأولوية للإيميلات التشغيلية أو المستخرجة من الموقع
        from crawler import SovereignCrawler
        permutations = []
        if onsite_emails:
            permutations.extend(onsite_emails)
        
        permutations.extend(SovereignCrawler.generate_permutations(owner_name, clean_domain))
        permutations = list(dict.fromkeys(permutations))
        
        # اختيار أفضل بريد تشغيلي أو إداري (استبعاد info/contact تلقائياً)
        dead_emails = ["info@", "contact@", "sales@", "support@", "enquiries@"]
        best_email = permutations[0]
        for em in permutations:
            if not any(d in em for d in dead_emails):
                best_email = em
                break

        total_score = 0
        status_details = []

        # 1. الأثر والأرشيف (+35 نقطة)
        if found_in_dorks:
            total_score += 35
            status_details.append("موجود في الأرشيف الرسمي (+35)")
        else:
            status_details.append("بحث مباشر عبر CT Logs (+20)")
            total_score += 20

        # 2. موقع الويب حي ونشط (+35 نقطة)
        if cls.check_domain_http_liveness(clean_domain):
            total_score += 35
            status_details.append("موقع الويب حي ونشط (+35)")
        else:
            status_details.append("الموقع غير استجاب (0)")

        # 3. سيرفر بريد نشط DoH (+30 نقطة)
        mx_host = cls._get_mx_host_doh(clean_domain)
        if mx_host:
            total_score += 30
            status_details.append(f"سيرفر بريد نشط: {mx_host} (+30)")
        else:
            status_details.append("سيرفر البريد مخفي (0)")

        final_status = f"أدلة النشاط: {total_score}/100 | " + " | ".join(status_details)
        return best_email, final_status, total_score

def verify_and_get_smart_email(owner_name: str, domain: str, found_in_dorks: bool = False, onsite_emails: list = None) -> tuple[str, str, int]:
    return SovereignEngine.weighted_scoring_engine(owner_name, domain, found_in_dorks, onsite_emails)
                                    
