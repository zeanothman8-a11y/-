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
        """
        استعلام سجلات MX عبر بروتوكول DNS over HTTPS (DoH) لتجاوز حظر المنافذ على السحابة
        """
        try:
            url = f"https://cloudflare-dns.com/dns-query?name={domain}&type=MX"
            headers = {"Accept": "application/dns-json"}
            response = httpx.get(url, headers=headers, timeout=5.0)
            if response.status_code == 200:
                data = response.json()
                answers = data.get("Answer", [])
                if answers:
                    mx_records = []
                    for ans in answers:
                        if ans.get("type") == 15: # MX Record Type
                            parts = ans.get("data", "").split()
                            if len(parts) >= 2:
                                mx_records.append((int(parts[0]), parts[1].rstrip('.')))
                    if mx_records:
                        mx_records.sort(key=lambda x: x[0])
                        return mx_records[0][1]
        except Exception:
            pass
        return None

    @staticmethod
    def check_domain_http_liveness(domain: str) -> bool:
        """
        فحص ما إذا كان الموقع يعمل وحياً عبر بروتوكول الويب
        """
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
        """
        نظام تقييم الطبقات التراكمي السيادي الصارم (بدون Gravatar، تركيز على الأرشيف والويب والـ MX)
        """
        clean_domain = domain.lower().replace("https://", "").replace("http://", "").replace("www.", "").strip("/")
        if not clean_domain:
            return "", "دومين غير صالح أو مفقود", 0

        permutations = []
        
        # إذا وجدنا إيميلات مباشرة من موقع الشركة أثناء الزحف العميق، نضعها في أولوية القائمة القصوى
        if onsite_emails:
            permutations.extend(onsite_emails)

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
        
        permutations = list(dict.fromkeys(permutations))
        best_email = permutations[0] if permutations else f"info@{clean_domain}"
        total_score = 0
        status_details = []

        # 1. الوجود في الأرشيف العميق و Dorks (+35 نقطة)
        if found_in_dorks:
            total_score += 35
            status_details.append("الوجود في الأرشيف (+35)")
        else:
            status_details.append("بدون أرشيف (0)")

        # 2. موقع الويب حي ونشط (+35 نقطة)
        is_live_web = cls.check_domain_http_liveness(clean_domain)
        if is_live_web:
            total_score += 35
            status_details.append("موقع الويب حي ونشط (+35)")
        else:
            status_details.append("الموقع غير استجاب للويب (0)")

        # 3. سيرفر البريد نشط عبر DoH (+30 نقطة)
        mx_host = cls._get_mx_host_doh(clean_domain)
        if mx_host:
            total_score += 30
            status_details.append(f"سيرفر البريد نشط DoH: {mx_host} (+30)")
        else:
            status_details.append("سيرفر البريد مخفي/محمي (0)")

        final_status = f"مؤشرات اليقين: {total_score}/100 | " + " | ".join(status_details)
        return best_email, final_status, total_score

def verify_and_get_smart_email(owner_name: str, domain: str, found_in_dorks: bool = False, onsite_emails: list = None) -> tuple[str, str, int]:
    email, status, score = SovereignEngine.weighted_scoring_engine(owner_name, domain, found_in_dorks, onsite_emails)
    return email, f"{status}", score
            
