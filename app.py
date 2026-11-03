import os
import io
import openpyxl
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
max_results = st.number_input("الحد الأقصى للنتائج الجديدة:", min_value=5, max_value=50, value=10, step=5)

start_button = st.button("🚀 بدء المحركات السيادية المتكاملة")
if start_button:
    st.info(f"🔍 جاري تشغيل محرك السحب لمدينة: {city}...")
    
    scraper = SovereignScraper(city=city, keyword=keyword, max_results=int(max_results) * 2) # سحب عدد أكبر لضمان وجود شركات جديدة غير مخزنة
    raw_leads = asyncio.run(scraper.scrape_maps())
    
    if raw_leads:
        st.success(f"تم سحب {len(raw_leads)} شركة مبدئياً من الخرائط. جاري الفلترة وتخطي المسجل مسبقاً...")
        
        crawler = SovereignCrawler(gemini_api_key=gemini_api_key)
        final_results = []
        progress_bar = st.progress(0)
        
        processed_count = 0
        for i, comp in enumerate(raw_leads):
            if processed_count >= int(max_results):
                break

            company_name = comp["company_name"]
            maps_link = comp["maps_link"]
                        # استخراج بيانات الهوية والدومين والبحث الأرشيفي العميق
            identity_data = asyncio.run(crawler.crawl_company_website(company_name, city))
            estimated_domain = identity_data["extracted_domain"]
            found_in_dorks = identity_data.get("found_in_dorks", False) # استلام حالة الـ Dorks
            
            if not estimated_domain:
                clean_comp_name = company_name.lower().replace(" ", "").replace(",", "").replace(".", "").replace("ltd", "").replace("limited", "")
                estimated_domain = f"{clean_comp_name}.co.uk" if "uk" in city.lower() else f"{clean_comp_name}.com"

            # منع التكرار
            existing_lead = db.check_existing_lead(estimated_domain)
            if existing_lead:
                print(f"[*] الشركة موجودة مسبقاً في القاعدة: {company_name} ({estimated_domain}) - يتم التخطي.")
                continue

            owner = identity_data["owner_name"]
            linkedin_profile = identity_data.get("linkedin_profile", "")
            source = identity_data["source"]

            permutations = crawler.generate_permutations(owner, estimated_domain)
            
            # تمرير حالة الـ found_in_dorks لنظام النقاط التراكمي في engine.py
            best_email, smtp_status = verify_and_get_smart_email(owner, estimated_domain, found_in_dorks)
            lead_record = {
                "company_name": company_name,
                "domain": estimated_domain,
                "maps_link": maps_link,
                "city": city,
                "decision_maker": owner,
                "linkedin_profile": linkedin_profile,
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
                "رابط لينكد إن": linkedin_profile if linkedin_profile else "غير متوفر",
                "مصدر الكشف": source,
                "أفضل إيميل مؤكد": best_email,
                "حالة فحص SMTP": smtp_status,
                "جميع الاحتمالات": permutations_str
            })
            
            processed_count += 1
            progress_bar.progress(min((i + 1) / len(raw_leads), 1.0))
        if final_results:
            df = pd.DataFrame(final_results)
            col1, col2 = st.columns(2)
            col1.metric("الشركات الجديدة المضافة", len(final_results))
            col2.metric("الإيميلات المتاحة", len(df))
            st.dataframe(df, use_container_width=True)
            # تصحيح طريقة حفظ وتصدير ملف الإكسل عبر BytesIO
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                df.to_excel(writer, index=False, sheet_name='Verilogix Leads')
            buffer.seek(0)

            st.download_button(
                label="📥 تحميل النتائج بصيغة xlsx",
                data=buffer,
                file_name=f"verilogix_leads_{city}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
    
        else:
            st.warning("⚠️ جميع الشركات المستخرجة موجودة مسبقاً في قاعدة البيانات! لم يتم إضافة شركات جديدة في هذه الدورة.")
    else:
        st.error("لم يتم العثور على نتائج من الخرائط.")
            
