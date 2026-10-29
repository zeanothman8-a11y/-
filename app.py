import os
import subprocess
import asyncio
import random
import socket
import streamlit as st
import pandas as pd
import google.generativeai as genai

from engine import verify_smtp_mailbox
from scraper import SovereignScraper
from crawler import SovereignCrawler
from notifier import TelegramNotifier

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
st.title("🛰️ نظام Verilogix AI السيادي: صائد الشركات وأصحاب القرار")

# شريط جانبي لإعدادات الذكاء الاصطناعي
st.sidebar.header("⚙️ إعدادات النظام")

# مدخلات المستخدم الأساسية
city = st.text_input("أدخل اسم المدينة والدولة (مثال: Rotterdam, Netherlands):", "Rotterdam, Netherlands")
keyword = st.text_input("الكلمة المفتاحية لنوع الشركة (مثال: Logistics companies):", "Logistics companies")
max_results = st.number_input("الحد الأقصى للنتائج المطلوب سحبها:", min_value=5, max_value=50, value=10, step=5)

# تعريف زر التشغيل في مكانه الصحيح قبل أي فحص
start_button = st.button("🚀 بدء المحركات السيادية المتكاملة")

# === التنفيذ الرئيسي عند الضغط على زر البحث ===
if start_button:
    st.info(f"🔍 جاري تشغيل محرك السحب السيادي لمدينة: {city}...")
    
    # 1. تشغيل المحرك الأول (سحب الخرائط)
    scraper = SovereignScraper(city=city, keyword=keyword, max_results=int(max_results))
    raw_leads = asyncio.run(scraper.scrape_maps())
    
    if raw_leads:
        st.success(f"تم بنجاح سحب {len(raw_leads)} شركة! جاري تفعيل محرك الزحف وتوليد الإيميلات وفحص الـ SMTP...")
        
        crawler = SovereignCrawler()
        final_results = []
        progress_bar = st.progress(0)
        
        for i, comp in enumerate(raw_leads):
            company_name = comp["company_name"]
            maps_link = comp["maps_link"]
            
            # استنتاج الدومين مبدئياً
            clean_comp_name = company_name.lower().replace(" ", "").replace(",", "").replace(".", "").replace("inc", "").replace("llc", "")
            estimated_domain = f"{clean_comp_name}.com"
            
            # 2. تشغيل المحرك الثاني (الزحف الداخلي وكشف صاحب القرار)
            identity_data = asyncio.run(crawler.crawl_company_website(estimated_domain))
            owner = identity_data["owner_name"]
            
            # 3. تشغيل المحرك الثالث (توليد مصفوفة الإيميلات)
            permutations = crawler.generate_permutations(owner, estimated_domain)
            best_email = permutations[0] if permutations else f"info@{estimated_domain}"
            
            # 4. تشغيل المحرك الرابع (فحص الـ SMTP العميق)
            smtp_status = verify_smtp_mailbox(best_email)
            
            final_results.append({
                "اسم الشركة": company_name,
                "رابط الخرائط": maps_link,
                "صاحب القرار": owner,
                "مصدر الكشف": identity_data["source"],
                "أفضل إيميل مؤكد": best_email,
                "حالة فحص SMTP": smtp_status,
                "جميع الاحتمالات": ", ".join(permutations[:3])
            })
            
            progress_bar.progress((i + 1) / len(raw_leads))
            
        df = pd.DataFrame(final_results)
        st.dataframe(df, use_container_width=True)
        
        # إرسال التنبيه عبر تليجرام عند الاكتمال بنجاح
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
