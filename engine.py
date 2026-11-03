import hashlib
import httpx
import random
import string

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
        فحص ما إذا كان الموقع يعمل وحياً عبر بروتوكول الويب (يتجاوز حظر المنافذ البريدية)
        """
        for proto in ["https", "http"]:
            try:
                res = httpx.head(f"{proto}://{domain}", timeout=4.0, follow_redirects=True, headers={"User-Agent": "Mozilla/5.0"})
                if res.status_code < 400:
                    return True
            except Exception:
                pass
        return False

    @staticmethod
    def check_gravatar(email: str) -> bool:
        clean_email = email.lower().strip()
        email_hash = hashlib.md5(clean_email.encode('utf-8')).hexdigest()
        url = f"https://www.gravatar.com/avatar/{email_hash}?d=404"
        try:
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) VerilogixAI/2.0"}
            response = httpx.get(url, headers=headers, timeout=3.0)
            if response.status_code == 200:
                return True
        except Exception:
            pass
        return False

    @classmethod
    def weighted_scoring_engine(cls, owner_name: str, domain: str, found_in_dorks: bool = False) -> tuple[str, str, int]:
        """
        نظام تقييم الطبقات التراكمي السيادي المقاوم للحظر السحابي
        """
        clean_domain = domain.lower().replace("https://", "").replace("http://", "").replace("www.", "").strip("/")
        if not clean_domain:
            return "غير محدد", "دومين غير صالح", 0

        permutations = []
        if owner_name and owner_name != "غير محدد":
            parts = owner_name.lower().split()
            if len(parts) >= 2:
                first, last = parts[0], parts[-1]
                permutations.extend([
                    f"{first}.{last}@{clean_domain}",
                    f"{first}{last}@{clean_domain}",
                    f"{first[0]}{last}@{clean_domain}",
                    f"{first[0]}.{last}@{clean_domain}",
                    f"{first}@{clean_domain}"
                ])
        
        # الأنماط التشغيلية كبدائل قوية
        permutations.extend([
            f"operations@{clean_domain}",
            f"dispatch@{clean_domain}",
            f"info@{clean_domain}",
            f"contact@{clean_domain}",
            f"sales@{clean_domain}"
        ])

        best_email = permutations[0]
        total_score = 0
        status_details = []

        # 1. فحص الوجود عبر Dorks والأرشيف (+35 نقطة)
        if found_in_dorks:
            total_score += 35
            status_details.append("وُجد في الأرشيف (+35)")
        else:
            total_score += 10
            status_details.append("بدون أرشيف (+10)")

        # 2. فحص Gravatar والهوية الرقمية (+25 نقطة)
        gravatar_found = False
        for email in permutations[:5]:
            if cls.check_gravatar(email):
                best_email = email
                gravatar_found = True
                total_score += 25
                status_details.append(f"Gravatar مؤكد (+25)")
                break

        # 3. فحص الوجود الحي عبر HTTPS/HTTP (بديل آمن لـ SMTP المحظور) (+25 نقطة)
        is_live_web = cls.check_domain_http_liveness(clean_domain)
        if is_live_web:
            total_score += 25
            status_details.append("موقع الشركة حي ونشط عبر الويب (+25)")
        else:
            status_details.append("الموقع غير استجاب للويب (0)")

        # 4. فحص سجلات الـ MX عبر DoH السحابي (+15 نقطة)
        mx_host = cls._get_mx_host_doh(clean_domain)
        if mx_host:
            total_score += 15
            status_details.append(f"سيرفر بريد نشط DoH: {mx_host} (+15)")
        else:
            status_details.append("سيرفر البريد مخفي/محمي (0)")

        # ضمان عدم هبوط النتيجة بشكل مزعج، واعتماد الحد الأدنى الذكي
        if total_score < 40 and not gravatar_found:
            best_email = f"operations@{clean_domain}"
            status_details.append("-> تحويل للإيميل التشغيلي الآمن")

        final_status = f"مؤشرات اليقين: {total_score}/100 | " + " | ".join(status_details)
        return best_email, final_status, total_score

def verify_and_get_smart_email(owner_name: str, domain: str, found_in_dorks: bool = False) -> tuple[str, str]:
    email, status, score = SovereignEngine.weighted_scoring_engine(owner_name, domain, found_in_dorks)
    return email, f"{status}"
                                
