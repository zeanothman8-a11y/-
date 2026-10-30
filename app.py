import os
import subprocess
import asyncio
import streamlit as st
import pandas as pd
import google.generativeai as genai
from engine import verify_and_get_smart_email
from scraper import SovereignScraper
from crawler import SovereignCrawler
from database import SovereignDatabase

try:
    gemini_api_key = st.secrets["api_keys"]["GEMINI_API_KEY"]
except Exception:
    gemini_api_key = ""

if gemini_api_key:
    genai.configure(api_key=gemini_api_key)

@st.cache_resource
def install_playwright():
    try:
        subprocess.run(["playwright", "install", "chromium"], check=True)
    except Exception as e:
        print(f"Notice during browser install: {e}")

install_playwright()

db = SovereignDatabase()

st.set_page_config(page_title="Verilogix AI Engine", layout="wide")
st.title("🛰️ نظام Verilogix AI السيادي: صائد الشركات وأصحاب القرار")

st.sidebar.header("⚙️ إعدادات البحث")
city = st.text_input("أدخل اسم المدينة والدولة:", "London, UK")
keyword = st.text_input("الكلمة المفتاحية لنوع الشركة:", "Logistics companies")
max_results = st.number_input("الحد الأقصى للنتائج:", min_value=5, max_value=50, value=10, step=5)

start_button = st.button("🚀 بدء المحركات السيادية المتكاملة")

if start_button:
    st.info(f"🔍 جاري تشغيل محرك السحب لمدينة: {city}...")
    
    scraper = SovereignScraper(city=city, keyword=keyword, max_results=int(max_results))
    raw_leads = asyncio.run(scraper.scrape_maps())
    
    if raw_leads:
        st.success(f"تم بنجاح سحب {len(raw_leads)} شركة! جاري استخراج البيانات الدقيقة والتحقق من سيرفرات MX...")
        
        crawler = SovereignCrawler(gemini_api_key=gemini_api_key)
        final_results = []
        progress_bar = st.progress(0)
        
        for i, comp in enumerate(raw_leads):
            company_name = comp["company_name"]
            maps_link = comp["maps_link"]
            
            # استدعاء البحث الذكي للعثور على الدومين الحقيقي للشركة مباشرة
            identity_data = asyncio.run(crawler.crawl_company_website(company_name, city))
            estimated_domain = identity_data["extracted_domain"]
            owner = identity_data["owner_name"]
            source = identity_data["source"]
            
            if not estimated_domain:
                # دومين احتياطي في حال تعذر العثور عليه
                clean_comp_name = company_name.lower().replace(" ", "").replace(",", "").replace(".", "").replace("ltd", "").replace("limited", "")
                estimated_domain = f"{clean_comp_name}.co.uk" if "uk" in city.lower() else f"{clean_comp_name}.com"

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
        
        col1, col2 = st.columns(2)
        col1.metric("إجمالي الشركات المعالجة", len(final_results))
        col2.metric("الإيميلات المتاحة", len(df))
        
        st.dataframe(df, use_container_width=True)
        
        csv_data = df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 تحميل النتائج بصيغة CSV",
            data=csv_data,
            file_name=f"verilogix_leads_{city}.csv",
            mime="text/csv"
        )
    else:
        st.error("لم يتم العثور على نتائج.")
            
