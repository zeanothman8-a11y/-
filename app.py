import os
import subprocess
import streamlit as st
import asyncio
import random
import pandas as pd
from playwright.async_api import async_playwright

# محاولة تثبيت متصفح Playwright تلقائياً على السيرفر السحابي
try:
  subprocess.run(["playwright", "install", "chromium"], check=True)
except Exception as e:
  print(f"Notice during browser install: {e}")
# إعداد واجهة Streamlit
st.set_page_config(page_title="Scraper Engine", layout="wide")
st.title("🛰️ المحرك الأول: صائد الشركات من خرائط جوجل")

# مدخلات المستخدم
city = st.text_input("أدخل اسم المدينة والكدولة (مثال: New York, USA):", "New York, USA")
keyword = st.text_input("الكلمة المفتاحية لنوع الشركة (مثال: Logistics companies):", "Logistics companies")
max_results = st.number_input("الحد الأقصى للنتائج المطلوب سحبها:", min_value=5, max_value=200, value=15, step=5)

start_button = st.button("🚀 بدء عملية الاستخراج")

async def scrape_google_maps(search_query, max_items):
    results = []
    
    async with async_playwright() as p:
        # تشغيل متصفح Chromium بمعلمات تفادي الكشف عن البوتات
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox"
            ]
        )
        
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            locale="en-US"
        )
        
        page = await context.new_page()
        
        # التوجه إلى خرائط جوجل
        url = f"https://www.google.com/maps/search/{search_query.replace(' ', '+')}"
        st.info(f"جاري الانتقال إلى: {url}")
        await page.goto(url, timeout=60000)
        await page.wait_for_timeout(3000)
        
        # محاكاة التمرير لأسفل لتحميل القائمة
        scroll_selector = 'div[role="feed"]'
        try:
            await page.wait_for_selector(scroll_selector, timeout=10000)
        except Exception:
            st.warning("لم يتم العثور على حاوية نتائج قياسية، جاري محاولة القراءة المباشرة...")
        
        collected_count = 0
        items_history = set()
        
        progress_bar = st.progress(0)
        
        for _ in range(15):  # محاولات التمرير
            if collected_count >= max_items:
                break
                
            # جلب جميع عناصر الشركات في الصفحة
            cards = await page.query_selector_all('a[href*="/maps/place/"]')
            
            for card in cards:
                if collected_count >= max_items:
                    break
                    
                href = await card.get_attribute("href")
                if href in items_history:
                    continue
                    
                items_history.add(href)
                
                # الحصول على الاسم بأسلوب آمن
                aria_label = await card.get_attribute("aria-label")
                if aria_label:
                    company_name = aria_label
                else:
                    company_name = await card.inner_text()
                    
                company_name = company_name.split('\n')[0].strip()
                
                if company_name and len(company_name) > 2:
                    results.append({
                        "اسم الشركة": company_name,
                        "رابط الخرائط": href
                    })
                    collected_count += 1
                    progress_bar.progress(min(collected_count / max_items, 1.0))
            
            # محاكاة سلوك بشري بالتمرير والانتظار العشوائي
            if await page.query_selector(scroll_selector):
                await page.eval_on_selector(scroll_selector, "el => el.scrollBy(0, 1000)")
                await page.wait_for_timeout(random.randint(1500, 3000))
        
        await browser.close()
    return results

if start_button:
    query = f"{keyword} in {city}"
    st.write(f"🔍 البحث عن: **{query}**")
    
    with st.spinner("جاري سحب البيانات ومحاكاة التصفح البشري..."):
        # تشغيل دالة async داخل Streamlit
        extracted_data = asyncio.run(scrape_google_maps(query, max_results))
        
    if extracted_data:
        st.success(f"تم العثور على {len(extracted_data)} شركة بنجاح!")
        df = pd.DataFrame(extracted_data)
        st.dataframe(df, use_container_width=True)
        
        # إمكانية تحميل النتائج
        csv_data = df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 تحميل البيانات بصيغة CSV",
            data=csv_data,
            file_filename=f"companies_{city}.csv",
            mime="text/csv"
        )
    else:
        st.error("لم يتم العثور على نتائج أو تم حجب الطلب. حاول تعديل الكلمات المفتاحية.")
      
