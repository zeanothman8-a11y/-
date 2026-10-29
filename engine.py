import socket
import smtplib
import dns.resolver
from pydantic import BaseModel, EmailStr
from tenacity import retry, stop_after_attempt, wait_exponential

# هيكل البيانات الصارم باستخدام Pydantic لضمان عدم تلف الداتا
class LeadModel(BaseModel):
    company_name: str
    decision_maker: str
    target_email: EmailStr
    whatsapp_number: str
    smtp_status: str

# محرك فحص الـ SMTP العميق (Deep Handshake) بدون إرسال إيميل فعلي
@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def verify_smtp_mailbox(email: str) -> str:
    domain = email.split('@')[1]
    try:
        # البحث عن خادم الـ MX الخاص بالشركة المستهدفة
        mx_records = dns.resolver.resolve(domain, 'MX')
        mx_host = str(mx_records[0].exchange)
        
        # الاتصال المباشر بخادم البريد (SMTP Handshake)
        server = smtplib.SMTP(timeout=10)
        server.connect(mx_host)
        server.helo('verilogix.ai')
        server.mail('admin@verilogix.ai')
        code, message = server.rcpt_to(email)
        server.quit()
        
        if code == 250:
            return "مؤكد 100% (صحيح ونشط)"
        else:
            return f"مرفوض من السيرفر (كود: {code})"
    except Exception as e:
        return f"فشل التحقق / حظر مؤقت: {str(e)}"

# محرك توليد وفحص الاحتمالات لأصحاب القرار
def generate_and_verify_leads(company_name: str, raw_owner_name: str, domain: str):
    clean_domain = domain.lower().replace("https://", "").replace("http://", "").replace("www.", "").strip("/")
    
    # مصفوفة توليد الإيميلات بناءً على اسم صاحب القرار
    permutations = []
    if raw_owner_name and raw_owner_name != "غير محدد":
        parts = raw_owner_name.lower().split()
        if len(parts) >= 2:
            first, last = parts[0], parts[-1]
            permutations = [
                f"{first}.{last}@{clean_domain}",
                f"{first}{last}@{clean_domain}",
                f"{first[0]}{last}@{clean_domain}",
                f"ceo@{clean_domain}",
                f"info@{clean_domain}"
            ]
    else:
        permutations = [f"info@{clean_domain}", f"contact@{clean_domain}", f"operations@{clean_domain}"]
    
    # فحص الإيميلات واستخراج الأول الصالح
    for email in permutations:
        status = verify_smtp_mailbox(email)
        if "مؤكد" in status:
            return email, status
            
    return permutations[0], "يحتاج فحص يدوي"
          
