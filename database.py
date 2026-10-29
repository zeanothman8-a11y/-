import os
import sqlite3
from datetime import datetime

# إذا كنت تستخدم Turso سحابياً عبر st.secrets، يمكنك جلب الرابط والتوكن، وإلا سيتم التراجع لقاعدة محلية SQLite آمنة
try:
    import streamlit as st
    TURSO_URL = st.secrets.get("turso", {}).get("DATABASE_URL", "verilogix_local.db")
    TURSO_TOKEN = st.secrets.get("turso", {}).get("AUTH_TOKEN", "")
except Exception:
    TURSO_URL = "verilogix_local.db"
    TURSO_TOKEN = ""

class SovereignDatabase:
    def __init__(self):
        self.init_db()

    def get_connection(self):
        """
        إنشاء اتصال آمن بقاعدة البيانات (يدعم Turso عبر libsql إذا توفرت الإعدادات أو SQLite المحلّي)
        """
        if TURSO_TOKEN and "libsql://" in TURSO_URL:
            try:
                import libsql_client
                return libsql_client.connect(url=TURSO_URL, auth_token=TURSO_TOKEN)
            except Exception as e:
                print(f"[!] تعذر الاتصال بـ Turso السحابي، التراجع للقاعدة المحلية: {e}")
        
        # الاتصال المحلي الاحتياطي عالي الأداء
        conn = sqlite3.connect("verilogix_local.db", check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self):
        """
        إنشاء الجداول الهيكلية السيادية لتخزين الشركات والإيميلات المؤكدة
        """
        conn = self.get_connection()
        if TURSO_TOKEN and "libsql://" in TURSO_URL:
            # تنفيذ عبر libsql client
            conn.execute("""
                CREATE TABLE IF NOT EXISTS verified_leads (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    company_name TEXT,
                    domain TEXT UNIQUE,
                    maps_link TEXT,
                    city TEXT,
                    decision_maker TEXT,
                    source TEXT,
                    target_email TEXT,
                    smtp_status TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
        else:
            with conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS verified_leads (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        company_name TEXT,
                        domain TEXT UNIQUE,
                        maps_link TEXT,
                        city TEXT,
                        decision_maker TEXT,
                        source TEXT,
                        target_email TEXT,
                        smtp_status TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
        print("[*] تم تهيئة قاعدة بيانات Verilogix AI بنجاح وتأمين الجداول.")

    def check_existing_lead(self, domain: str) -> dict | None:
        """
        التحقق مما إذا كان الدومين مفحوصاً مسبقاً لتوفير الوقت وضمان سرعة الاسترجاع الفوري
        """
        conn = self.get_connection()
        clean_domain = domain.lower().strip()
        
        if TURSO_TOKEN and "libsql://" in TURSO_URL:
            try:
                res = conn.execute("SELECT * FROM verified_leads WHERE domain = ?", (clean_domain,))
                row = res.fetchone()
                if row:
                    return dict(zip(res.columns, row))
            except Exception:
                pass
            return None
        else:
            with conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM verified_leads WHERE domain = ?", (clean_domain,))
                row = cursor.fetchone()
                if row:
                    return dict(row)
            return None

    def save_lead(self, lead_data: dict):
        """
        حفظ الشركة وإيميلها المؤكد نهائياً في قاعدة البيانات السيادية
        """
        conn = self.get_connection()
        clean_domain = lead_data.get("domain", "").lower().strip()
        
        if not clean_domain:
            return

        if TURSO_TOKEN and "libsql://" in TURSO_URL:
            try:
                conn.execute("""
                    INSERT OR REPLACE INTO verified_leads 
                    (company_name, domain, maps_link, city, decision_maker, source, target_email, smtp_status, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    lead_data.get("company_name"),
                    clean_domain,
                    lead_data.get("maps_link"),
                    lead_data.get("city"),
                    lead_data.get("decision_maker"),
                    lead_data.get("source"),
                    lead_data.get("target_email"),
                    lead_data.get("smtp_status"),
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                ))
            except Exception as e:
                print(f"[!] خطأ في حفظ البيانات سحابياً: {e}")
        else:
            with conn:
                conn.execute("""
                    INSERT OR REPLACE INTO verified_leads 
                    (company_name, domain, maps_link, city, decision_maker, source, target_email, smtp_status, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    lead_data.get("company_name"),
                    clean_domain,
                    lead_data.get("maps_link"),
                    lead_data.get("city"),
                    lead_data.get("decision_maker"),
                    lead_data.get("source"),
                    lead_data.get("target_email"),
                    lead_data.get("smtp_status"),
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                ))
          
