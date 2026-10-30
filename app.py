import os
import subprocess
import asyncio
import random
import socket
import streamlit as st
import pandas as pd
import google.generativeai as genai
from engine import verify_and_get_smart_email
from scraper import SovereignScraper
from crawler import SovereignCrawler
from notifier import TelegramNotifier
from database import SovereignDatabase

# استدعاء الأسرار بأمان تام من سيرفر المنصة السحابية
try:
    gemini_api_key = st.secrets["api_keys"]["GEMINI_API_KEY"]
    telegram_token = st.secrets["api_keys"]["TELEGRAM_TOKEN"]
    telegram_chat_id = st.secrets["api_keys"]["TELEGRAM_CHAT_ID"]
except Exception:
    gemini_api_key = ""
    telegram_token = ""
    telegram_chat_id = ""

if gemini_api_key:
    genai.configure(api_key=gemini_api_key)

# تثبيت متصفح Playwright تلقائياً على السيرفر السحابي
@st.cache_resource
def install_playwright():
    try:
        subprocess.run(["playwright", "install", "chromium"], check=True)
    except Exception as e:
        print(f"Notice during browser install: {e}")

install_playwright()

# تهيئة قاعدة البيانات السيادية
db = SovereignDatabase()

# إعداد واجهة Streamlit
st.set_page_config(page_title="Verilogix AI Engine", layout="wide")
st.title("🛰️ نظام Verilogix AI السيادي: صائد الشركات وأصحاب القرار")

# شريط جانبي لإعدادات الذكاء الاصطناعي والتصفية المتقدمة
st.sidebar.header("⚙️ إعدادات النظام والتصفية")

city = st.text_input("أدخل اسم المدينة والدولة (مثال: Rotterdam, Netherlands):", "Rotterdam, Netherlands")
keyword = st.text_input("الكلمة المفتاحية لنوع الشركة (مثال: Logistics companies):", "Logistics companies")
max_results = st.number_input("الحد الأقصى للنتائج المطلوب سحبها:", min_value=5, max_value=50, value=10, step=5)

st.sidebar.markdown("---")
st.sidebar.subheader("🎯 تصفية جودة الإيميلات للحملات")
only_high_confidence = st.sidebar.checkbox("عرض الإيميلات المؤكدة فقط (درجة يقين عالية 85% - 100%)", value=False)

start_button = st.button("🚀 بدء المحركات السيادية المتكاملة")

# === التنفيذ الرئيسي عند الضغط على زر البحث ===
if start_button:
    st.info(f"🔍 جاري تشغيل محرك السحب السيادي لمدينة: {city}...")
    
    scraper = SovereignScraper(city=city, keyword=keyword, max_results=int(max_results))
    raw_leads = asyncio.run(scraper.scrape_maps())
    
    if raw_leads:
        st.success(f"تم بنجاح سحب {len(raw_leads)} شركة! جاري فحص البيانات والتحقق من أصحاب القرار والإيميلات...")
        
        crawler = SovereignCrawler(gemini_api_key=gemini_api_key)
        final_results = []
        progress_bar = st.progress(0)
        
        for i, comp in enumerate(raw_leads):
            company_name = comp["company_name"]
            maps_link = comp["maps_link"]
            
            clean_comp_name = company_name.lower().replace(" ", "").replace(",", "").replace(".", "").replace("inc", "").replace("llc", "").replace("bv", "")
            estimated_domain = f"{clean_comp_name}.com"
            
            # جلب وإعادة فحص البيانات حياً في كل مرة دون التوقف عند التخزين السابق
            identity_data = asyncio.run(crawler.crawl_company_website(estimated_domain))
            owner = identity_data["owner_name"]
            source = identity_data["source"]
            
            permutations = crawler.generate_permutations(owner, estimated_domain)
            best_email, smtp_status = verify_and_get_smart_email(owner, estimated_domain)
            
            lead_record = {
                "company_name": company_name,
                "domain": estimated_domain,
                "maps_link": maps_link,
                "city": city,
                "decision_maker": owner,
                "source": source,
                "target_email": best_email,
                "smtp_status": smtp_status
            }
            db.save_lead(lead_record)
            permutations_str = ", ".join(permutations[:3]) if permutations else best_email
            
            final_results.append({
                "اسم الشركة": company_name,
                "رابط الخرائط": maps_link,
                "صاحب القرار": owner,
                "مصدر الكشف": source,
                "أفضل إيميل مؤكد": best_email,
                "حالة فحص SMTP": smtp_status,
                "جميع الاحتمالات": permutations_str
            })
            
            progress_bar.progress((i + 1) / len(raw_leads))
            
        df = pd.DataFrame(final_results)
        
        # تطبيق الفلترة المتقدمة بناءً على رغبة المستخدم
        if only_high_confidence:
            df = df[df["حالة فحص SMTP"].str.contains(r"100%|95%|90%|88%", na=False)]
        
        # عرض مؤشرات الأداء السريعة
        col1, col2 = st.columns(2)
        col1.metric("إجمالي الشركات المعالجة", len(final_results))
        col2.metric("الإيميلات المتاحة بعد التصفية", len(df))
        
        st.dataframe(df, use_container_width=True)
        
        if telegram_token and telegram_chat_id:
            try:
                notifier = TelegramNotifier(telegram_token, telegram_chat_id)
                summary_msg = f"🚀 *تم سحب وفحص الشركات بنجاح عبر Verilogix AI!*\n📍 المدينة: {city}\n📊 الشركات المطابقة للفلتر: {len(df)}\n✅ جاهزة للتواصل المباشر."
                notifier.send_alert(summary_msg)
            except Exception as e:
                st.warning(f"تعذر إرسال التنبيه: {e}")
                
        csv_data = df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 تحميل النتائج المصفاة بصيغة CSV للحملات",
            data=csv_data,
            file_name=f"verilogix_targeted_leads_{city}.csv",
            mime="text/csv"
        )
    else:
        st.error("لم يتم العثور على نتائج. تأكد من الكلمات المفتاحية أو جرب زيادة وقت الانتظار.")
