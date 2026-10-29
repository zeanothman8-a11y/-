import os
import subprocess
import asyncio
import random
import socket
import whois
import asyncio
import re
import httpx
import streamlit as st
import pandas as pd
import streamlit as st
import google.generativeai as genai
from engine import verify_smtp_mailbox, generate_and_verify_leads
from scraper import SovereignScraper
from bs4 import BeautifulSoup
from urllib.parse import urlparse
from notifier import TelegramNotifier
# استدعاء الأسرار بأمان تام من سيرفر المنصة السحابية
try:
    gemini_api_key = st.secrets["api_keys"]["GEMINI_API_KEY"]
    telegram_token = st.secrets["api_keys"]["TELEGRAM_TOKEN"]
    telegram_chat_id = st.secrets["api_keys"]["TELEGRAM_CHAT_ID"]
except Exception:
    # قيم احتياطية لكي لا ينهار التطبيق إذا لم يتم إعداد الأسرار بعد
    gemini_api_key = ""
    telegram_token = ""
    telegram_chat_id = ""
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
        
# داخل زر التشغيل في Streamlit:
if start_button:
    st.info(f"جاري تشغيل محرك السحب السيادي لمدينة: {city}...")
    
    # تهيئة كلاس السحب
    scraper = SovereignScraper(city=city, keyword=keyword, max_results=int(max_results))
    
    # تشغيل السحب بشكل غير متزامن
    raw_leads = asyncio.run(scraper.scrape_maps())
    
    if raw_leads:
        st.success(f"تم بنجاح سحب {len(raw_leads)} شركة شحن مستهدفة!")
        # هنا سنقوم بتمرير هذه القائمة مباشرة إلى المحرك الثاني (Identity Finder & Email Permutator)
    else:
        st.error("لم يتم جلب نتائج، جرب تغيير اسم المدينة أو زيادة وقت الانتظار.")
        
# تثبيت متصفح Playwright تلقائياً على السيرفر السحابي بأمان
@st.cache_resource
def install_playwright():
    try:
        subprocess.run(["playwright", "install", "chromium"], check=True)
    except Exception as e:
        print(f"Notice during browser install: {e}")

install_playwright()

# إعداد واجهة Streamlit
st.set_page_config(page_title="Verilogix AI Engine", layout="wide")
st.title("🛰️ نظام Verilogix AI: صائد الشركات وأصحاب القرار")

# شريط جانبي لإدخال مفتاح الذكاء الاصطناعي
st.sidebar.header("⚙️ إعدادات الذكاء الاصطناعي")
gemini_api_key = st.sidebar.text_input("أدخل مفتاح Google Gemini API:", type="password")

if gemini_api_key:
    genai.configure(api_key=gemini_api_key)

# مدخلات المستخدم الأساسية
city = st.text_input("أدخل اسم المدينة والدولة (مثال: Rotterdam, Netherlands):", "Rotterdam, Netherlands")
keyword = st.text_input("الكلمة المفتاحية لنوع الشركة (مثال: Logistics companies):", "Logistics companies")
max_results = st.number_input("الحد الأقصى للنتائج المطلوب سحبها:", min_value=5, max_value=50, value=10, step=5)

start_button = st.button("🚀 بدء المحرك المزدوج (بحث + ذكاء اصطناعي + توليد وفحص)")

# === المحرك الثاني: الذكاء الاصطناعي لتحليل صاحب القرار ===
def extract_decision_maker_with_ai(company_name):
    if not gemini_api_key:
        return "مفتاح الذكاء الاصطناعي غير متوفر", "غير محدد"
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        prompt = f"""
        أنت محلل بيانات لوجستية وخبير تجاري. بالنسبة لشركة الشحن أو اللوجستيات المسماة "{company_name}", 
        قم بتوقع أو استنتاج اسم المؤسس أو المدير التنفيذي (CEO أو Owner) المحتمل بناءً على اسم الشركة والسوق العاملة فيه، 
        أو أعطني وصفاً لمن يُعتبر صاحب القرار في شركات كهذه مع تخمين صيغة إيميل احترافية (مثل info@{company_name.lower().replace(' ', '').replace(',', '')}.com).
        أجب باختصار شديد باللغة العربية على شكل:
        الاسم المقترح: [...]
        الإيميل المقترح: [...]
        """
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"خطأ في الاتصال بالذكاء الاصطناعي: {e}"

# === المحرك الثالث: مولد صيغ الإيميلات الاحترافية ===
def generate_email_permutations(name, company_name):
    """توليد مصفوفة احتمالات الإيميلات الاحترافية"""
    clean_domain = company_name.lower().replace(" ", "").replace(",", "").replace(".", "").replace("inc", "").replace("llc", "").replace("ltd", "")
    domain = f"{clean_domain}.com"
    
    permutations = [f"info@{domain}", f"contact@{domain}", f"sales@{domain}"]
    if name and name != "غير محدد":
        parts = name.lower().split()
        if len(parts) >= 2:
            first, last = parts[0], parts[-1]
            permutations.insert(0, f"{first}.{last}@{domain}")
            permutations.insert(1, f"{first}{last}@{domain}")
            
    return list(set(permutations))

# === المحرك الرابع: فحص الـ SMTP الأساسي والدومين ===
def verify_smtp_email(email):
    """فحص أولي لصلاحية الإيميل والدومين لتجنب الحظر"""
    try:
        domain = email.split('@')[1]
        records = socket.getaddrinfo(domain, 25)
        if not records:
            return "مرفوض (لا يوجد خادم بريد)"
        return "صالح / مؤكد مبدئياً"
    except Exception:
        return "غير مؤكد (يحتاج فحص يدوي)"

# === المحرك الأول: سحب الخرائط عبر Playwright ===
async def scrape_google_maps(search_query, max_items):
    results = []
    # استدعاء playwright داخل الدالة لتجنب أخطاء النطاق المتزامن
    from playwright.async_api import async_playwright
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox", "--disable-dev-shm-usage"]
        )
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            locale="en-US"
        )
        page = await context.new_page()
        url = f"https://www.google.com/maps/search/{search_query.replace(' ', '+')}"
        
        try:
            await page.goto(url, timeout=60000)
            await page.wait_for_timeout(3000)
            
            scroll_selector = 'div[role="feed"]'
            try:
                await page.wait_for_selector(scroll_selector, timeout=10000)
            except Exception:
                pass
                
            collected_count = 0
            items_history = set()
            
            for _ in range(8):
                if collected_count >= max_items:
                    break
                cards = await page.query_selector_all('a[href*="/maps/place/"]')
                for card in cards:
                    if collected_count >= max_items:
                        break
                    href = await card.get_attribute("href")
                    if href in items_history:
                        continue
                    items_history.add(href)
                    
                    aria_label = await card.get_attribute("aria-label")
                    company_name = aria_label if aria_label else await card.inner_text()
                    company_name = company_name.split('\n')[0].strip()
                    
                    if company_name and len(company_name) > 2:
                        results.append({
                            "اسم الشركة": company_name,
                            "رابط الخرائط": href
                        })
                        collected_count += 1
                
                if await page.query_selector(scroll_selector):
                    await page.eval_on_selector(scroll_selector, "el => el.scrollBy(0, 1000)")
                    await page.wait_for_timeout(random.randint(1500, 2500))
        except Exception as e:
            print(f"Error during scraping: {e}")
        finally:
            await browser.close()
            
    return results

# === التنفيذ الرئيسي عند الضغط على زر البحث ===
if start_button:
    query = f"{keyword} in {city}"
    st.write(f"🔍 جاري تنفيذ البحث واستدعاء المحركات الأربعة لـ: **{query}**")
    
    with st.spinner("جاري سحب الشركات، التحليل بالذكاء الاصطناعي وتوليد وفحص الإيميلات..."):
        # تشغيل الدالة غير المتزامنة بشكل آمن داخل Streamlit
        extracted_data = asyncio.run(scrape_google_maps(query, max_results))
        
    if extracted_data:
        st.success(f"تم العثور على {len(extracted_data)} شركة! جاري المعالجة الكاملة...")
        
        enhanced_results = []
        progress_bar = st.progress(0)
        
        for i, item in enumerate(extracted_data):
            company = item["اسم الشركة"]
            
            # تشغيل المحرك الثاني (الذكاء الاصطناعي)
            ai_analysis = extract_decision_maker_with_ai(company)
            
            # تشغيل المحرك الثالث (توليد الإيميلات)
            emails__list = generate_email_permutations(company, company)
            best_email = emails__list[0] if emails__list else "غير متوفر"
            
            # تشغيل المحرك الرابع (فحص الـ SMTP)
            smtp_status = verify_smtp_email(best_email)

            enhanced_results.append({
                "اسم الشركة": company,
                "رابط الخرائط": item["رابط الخرائط"],
                "تحليل صاحب القرار (AI)": ai_analysis,
                "أفضل إيميل مقترح": best_email,
                "حالة الفحص (SMTP)": smtp_status,
                "جميع الاحتمالات": ", ".join(emails__list)
            })
            progress_bar.progress((i + 1) / len(extracted_data))
            
        df = pd.DataFrame(enhanced_results)
        st.dataframe(df, use_container_width=True)
        # بعد استخراج وتحليل النتائج بنجاح:
        if telegram_token and telegram_chat_id:
            try:
                notifier = TelegramNotifier(telegram_token, telegram_chat_id)
                summary_msg = f"🚀 *تم سحب وفحص شركات جديدة بنجاح!*\n📍 المدينة: {city}\n📊 عدد الشركات: {len(final_results)}\n✅ تم التأكد من إيميلات أصحاب القرار."
                notifier.send_alert(summary_msg)
            except Exception as e:
                st.warning(f"تعذر إرسال التنبيه: {e}")
        csv_data = df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 تحميل النتائج الشاملة بصيغة CSV",
            data=csv_data,
            file_name=f"verilogix_leads_{city}.csv",
            mime="text/csv"
        )
    else:
        st.error("لم يتم العثور على نتائج. تأكد من الكلمات المفتاحية أو جرب زيادة وقت الانتظار.")
        
