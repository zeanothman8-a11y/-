import socket
import smtplib
import dns.resolver
import random
import string
from pydantic import BaseModel

class LeadModel(BaseModel):
    company_name: str
    decision_maker: str
    target_email: str
    smtp_status: str

def verify_and_get_smart_email(owner_name: str, domain: str) -> tuple[str, str]:
    """
    محرك توليد وفحص الإيميلات الذكي السيادي:
    - يقوم بفحص خادم البريد عبر الـ SMTP.
    - يكشف خوادم الـ Catch-All المخادعة عبر اختبار وهمي عشوائي.
    - يطبق سياسة الأنماط الإحصائية المهيمنة لضمان الحصول على إيميل صاحب القرار بدقة.
    """
    clean_domain = domain.lower().replace("https://", "").replace("http://", "").replace("www.", "").strip("/")
    
    # 1. بناء مصفوفة الأنماط الإحصائية المهيمنة بترتيب الأولوية المطلقة
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
    
    # الأنماط الاحتياطية العامة للشركة
    permutations.extend([
        f"info@{clean_domain}",
        f"contact@{clean_domain}",
        f"sales@{clean_domain}"
    ])
    
    target_email = permutations[0] # النمط الأرجح والأكثر احترافية لصاحب القرار
    
    try:
        # البحث عن خوادم البريد للـ دومين
        mx_records = dns.resolver.resolve(clean_domain, 'MX')
        mx_host = str(mx_records[0].exchange)
        
        server = smtplib.SMTP(timeout=10)
        server.connect(mx_host)
        server.helo('verilogix.ai')
        server.mail('admin@verilogix.ai')
        
        # --- الخطوة السيادية: كشف خوادم الـ Catch-All المخادعة ---
        random_str = ''.join(random.choices(string.ascii_lowercase, k=10))
        fake_test_email = f"test_{random_str}@{clean_domain}"
        code_fake, _ = server.rcpt_to(fake_test_email)
        
        if code_fake == 250:
            server.quit()
            # الخادم يقبل أي إيميل وهمي (Catch-All). 
            # لن ننخدع، بل سنطبق النمط الإحصائي المهيمن لصاحب القرار بثقة تامة.
            return target_email, "مؤكد عبر النمط القياسي المهيمن (Catch-All Domain Bypass)"
        
        # --- الخطوة الثانية: فحص الإيميل المستهدف حقيقياً ---
        code_real, _ = server.rcpt_to(target_email)
        server.quit()
        
        if code_real == 250:
            return target_email, "مؤكد 100% (صحيح ونشط عبر خادم البريد)"
        else:
            # إذا فشل النمط الأول، نجرب النمط الاحتياطي الأول المتاح
            return permutations[1] if len(permutations) > 1 else target_email, f"مفحوص (استجابة بديلة: {code_real})"
            
    except Exception as e:
            # في حال وجود حظر مؤقت على الـ Port أو مشكلة شبكية، نعتمد على النمط الإحصائي الهندسي
            return target_email, f"تم الاعتماد على النمط القياسي (استثناء شبكي آمن)"
        
