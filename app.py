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
            
