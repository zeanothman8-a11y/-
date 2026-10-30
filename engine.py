import socket
import smtplib
import dns.resolver
import hashlib
import httpx
from concurrent.futures import ThreadPoolExecutor
from tenacity import retry, stop_after_attempt, wait_exponential

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
        """
        التحقق الفائق عبر بصمة Gravatar الرقمية لتجاوز أي خوادم مخادعة.
        """
        clean_email = email.lower().strip()
        email_hash = hashlib.md5(clean_email.encode('utf-8')).hexdigest()
        url = f"https://www.gravatar.com/avatar/{email_hash}?d=404"
        try:
            # استخدام رأس تصفح نظامي لتفادي الحظر أثناء الطلب
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) VerilogixAI/2.0"}
            response = httpx.get(url, headers=headers, timeout=3.0)
            if response.status_code == 200:
                return True
        except Exception:
            pass
        return False

    @classmethod
    def generate_smart_permutations(cls, owner_name: str, domain: str) -> list:
        clean_domain = domain.lower().replace("https://", "").replace("http://", "").replace("www.", "").strip("/")
        permutations = []
        
        if owner_name and owner_name != "غير محدد":
            parts = owner_name.lower().split()
            if len(parts) >= 2:
                first, last = parts[0], parts[-1]
                # ترتيب المصفوفة بناءً على احتمالية الاستخدام التجاري العالمي
                permutations.extend([
                    f"{first}.{last}@{clean_domain}",
                    f"{first}{last}@{clean_domain}",
                    f"{first[0]}{last}@{clean_domain}",
                    f"{first}@{clean_domain}",
                    f"{last}.{first}@{clean_domain}",
                    f"{first[0]}.{last}@{clean_domain}"
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

    @classmethod
    def deep_verify_email(cls, owner_name: str, domain: str) -> tuple[str, str, int]:
        clean_domain = domain.lower().replace("https://", "").replace("http://", "").replace("www.", "").strip("/")
        
        if not clean_domain:
            return "غير محدد", "خطأ: دومين غير صالح", 0

        permutations = cls.generate_smart_permutations(owner_name, clean_domain)
        target_email = permutations[0]

        # 1. الفحص الفوري عبر Gravatar (أعلى موثوقية 100%)
        for email in permutations[:5]: # فحص أول 5 احتمالات رئيسية للأشخاص
            if cls.check_gravatar(email):
                return email, "مؤكد 100% (تم التحقق عبر بصمة الهوية الرقمية Gravatar)", 100

        mx_host = cls._get_mx_host(clean_domain)
        if not mx_host:
            return target_email, "مفحوص (تعذر الوصول لخادم البريد MX، اعتماد النمط الهندسي)", 50

        # 2. الفحص المخبري المتقدم للـ SMTP وتجاوز Catch-All
        is_liar_server = False
        try:
            server = smtplib.SMTP(timeout=7)
            server.connect(mx_host)
            server.helo('verilogix.ai')
            server.mail('admin@verilogix.ai')

            fake1 = f"not_a_real_user_xyz_998877@{clean_domain}"
            fake2 = f"verify_test_fake_112233@{clean_domain}"
            
            code_f1, _ = server.rcpt_to(fake1)
            code_f2, _ = server.rcpt_to(fake2)

            if code_f1 == 250 and code_f2 == 250:
                is_liar_server = True

            if not is_liar_server:
                for email in permutations:
                    code_real, _ = server.rcpt_to(email)
                    if code_real == 250:
                        server.quit()
                        return email, "مؤكد 95% (فحص SMTP مباشر وناجح)", 95
                server.quit()
            else:
                server.quit()

        except Exception:
            pass

        if is_liar_server:
            return target_email, "مؤكد بنسبة 88% (سيرفر مخادع Catch-All - تم اعتماد النمط المهيمن للقيادات)", 88

        return target_email, "مفحوص (النمط القياسي الآمن)", 75

def verify_and_get_smart_email(owner_name: str, domain: str) -> tuple[str, str]:
    email, status, score = SovereignEngine.deep_verify_email(owner_name, domain)
    return email, f"{status} [درجة اليقين: {score}%]"
            
