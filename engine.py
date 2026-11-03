import socket
import smtplib
import dns.resolver
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
    def _get_mx_host(domain: str) -> str:
        try:
            records = dns.resolver.resolve(domain, 'MX')
            sorted_mx = sorted(records, key=lambda r: r.preference)
            return str(sorted_mx[0].exchange).rstrip('.')
        except Exception:
            return None

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
    def double_blind_smtp_check(cls, email: str, domain: str) -> tuple[bool, bool, str]:
        """
        استراتيجية الاختبار الثنائي المعكوس (Double-Blind Validation)
        لفحص ما إذا كان السيرفر حقيقياً أم مزيفاً (Catch-All)
        """
        mx_host = cls._get_mx_host(domain)
        if not mx_host:
            return False, False, "سيرفر MX غير متوفر"

        # توليد إيميل عشوائي مستحيل الوجود لكشف كذب السيرفر
        rand_str = ''.join(random.choices(string.ascii_lowercase + string.digits, k=10))
        fake_email = f"random_{rand_str}@{domain}"

        is_valid = False
        is_catch_all = False
        smtp_message = "فحص عادي"

        try:
            server = smtplib.SMTP(mx_host, timeout=6)
            server.helo("verilogix.ai")
            server.mail("audit@verilogix.ai")

            # 1. اختبار الإيميل الوهمي أولاً
            code_fake, _ = server.rcpt(fake_email)
            if code_fake == 250:
                is_catch_all = True

            # 2. اختبار الإيميل المستهدف الحقيقي
            code_target, _ = server.rcpt(email)
            if code_target == 250:
                is_valid = True

            server.quit()

            if is_catch_all:
                smtp_message = "سيرفر مخادع (Catch-All نشط)"
            elif code_target == 550:
                smtp_message = "مرفوض (User Unknown - دقة تامة)"
            elif is_valid:
                smtp_message = "مؤكد 250 OK (سيرفر صادق)"
            else:
                smtp_message = f"استجابة SMTP: {code_target}"

        except Exception as e:
            smtp_message = f"خطأ اتصال SMTP: {str(e)}"

        return is_valid, is_catch_all, smtp_message

    @classmethod
    def weighted_scoring_engine(cls, owner_name: str, domain: str, found_in_dorks: bool = False) -> tuple[str, str, int]:
        """
        نظام تقييم الطبقات التراكمي (Weighted Scoring Matrix)
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
        
        # الأنماط التشغيلية كبدائل آمنة
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

        # 1. التحقق من الأرشيف/Dorks (+40 نقطة)
        if found_in_dorks:
            total_score += 40
            status_details.append("وُجد في الأرشيف/Dorks (+40)")

        # 2. فحص Gravatar (+20 نقطة)
        gravatar_found = False
        for email in permutations[:5]:
            if cls.check_gravatar(email):
                best_email = email
                gravatar_found = True
                total_score += 20
                status_details.append(f"Gravatar مؤكد لـ {email} (+20)")
                break

        # 3. الاختبار الثنائي المعكوس (Double-Blind SMTP)
        is_valid, is_catch_all, smtp_msg = cls.double_blind_smtp_check(best_email, clean_domain)
        
        if not is_catch_all and is_valid:
            total_score += 30
            status_details.append("SMTP صادق وغير Catch-All (+30)")
        elif is_catch_all:
            status_details.append("Catch-All مكتشف (تحييد الخداع)")
        else:
            total_score += 10
            status_details.append(smtp_msg)

        # عتبة الاعتماد السيادية (أقل من 70 يتحول تلقائياً لاحتياطي operations لضمان عدم تلف البيانات)
        if total_score < 70 and not gravatar_found:
            best_email = f"operations@{clean_domain}"
            status_details.append("دون الحد الأدنى -> تحويل لاحتياطي (operations)")

        final_status = f"مؤشرات اليقين: {total_score}/100 | " + " | ".join(status_details)
        return best_email, final_status, total_score

def verify_and_get_smart_email(owner_name: str, domain: str, found_in_dorks: bool = False) -> tuple[str, str]:
    email, status, score = SovereignEngine.weighted_scoring_engine(owner_name, domain, found_in_dorks)
    return email, f"{status}"
            
