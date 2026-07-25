import asyncio
import json
import os
from datetime import datetime, timedelta
from playwright.async_api import async_playwright
from telegram import Bot
from groq import Groq

# ==========================================
# 1. CONFIGURATION - MATCHING YOUR CV
# ==========================================
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")

MY_CV = """
Sarah Samir PMP - CX and Operations Leader
Extensive BPO and Program Management experience
Certified PMP, Six Sigma, COPC professional
Specialized in:
- Operations Management
- Program/Project Management
- Customer Experience (CX) Management
- Contact Center Operations
- Quality & Training Management
- Business Process Outsourcing (BPO)
- Team Leadership (multi-site, multicultural)
- Client Relationship Management
- Workforce Management
- Sales Operations & E-commerce
- French language support operations
Looking for: Operations Manager, Program Manager, CX Manager, Contact Center Manager roles
Location: Cairo, Egypt (or Remote)
Expected salary: Competitive
"""

# KEYWORDS MATCHING YOUR PROFILE
SEARCH_KEYWORDS = "Operations Manager Program Manager CX Manager Contact Center"
MAX_JOB_AGE_DAYS = 14  # Last 2 weeks for management roles

# ==========================================
# 2. AI MATCHING (Groq Free API)
# ==========================================
groq_client = Groq(api_key=GROQ_API_KEY)

def analyze_job_with_ai(job_raw_text):
    prompt = f"""
    You are an expert technical recruiter analyzing job postings.
    
    Here is my CV/Profile: {MY_CV}
    Here is the raw text of a job posting: {job_raw_text}

    IMPORTANT REQUIREMENTS:
    1. Location MUST be: Cairo/Egypt, OR Remote, OR "Middle East/North Africa" region
    2. Job should be recently posted (extract the posting date if available)
    3. Role should match: Operations Management, Program Management, CX, Contact Center, BPO, Project Management
    
    Analyze the job and return a JSON object with:
    - "title": Job title
    - "company": Company name
    - "location": Exact location as stated
    - "salary": Salary if mentioned, otherwise "Not stated"
    - "posted_date": The posting date if available, otherwise "Unknown"
    - "description": A brief 2-3 sentence summary
    - "link": The URL to apply
    - "match_score": Integer 0-100 for CV match
    - "is_valid_location": true/false (true ONLY if: Cairo, Egypt, Giza, Alexandria, Remote, MENA region, OR remote-friendly)
    - "is_remote": true/false (true if job mentions Remote, Work from Home, WFH, Virtual)
    - "reason": 1-sentence explanation of the score

    Return ONLY valid JSON.
    """
    
    try:
        response = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            response_format={ "type": "json_object" },
            temperature=0.1
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        print(f"AI Error: {e}")
        return None

def is_job_recent(posted_date_str):
    """Check if the job was posted within MAX_JOB_AGE_DAYS"""
    if not posted_date_str or posted_date_str.lower() == "unknown":
        return True
    
    posted_date_str = posted_date_str.lower()
    
    if "day" in posted_date_str:
        try:
            days_ago = int(''.join(filter(str.isdigit, posted_date_str)))
            return days_ago <= MAX_JOB_AGE_DAYS
        except:
            return True
    
    if "week" in posted_date_str:
        try:
            weeks_ago = int(''.join(filter(str.isdigit, posted_date_str)))
            return weeks_ago <= 2  # Within 2 weeks
        except:
            return True
    
    if "month" in posted_date_str:
        return False  # Too old
    
    return True

# ==========================================
# 3. TELEGRAM NOTIFICATION
# ==========================================
async def send_job_to_telegram(job_data):
    bot = Bot(token=TELEGRAM_BOT_TOKEN)
    
    remote_badge = "🌍 *REMOTE*" if job_data.get('is_remote', False) else ""
    age_note = ""
    if not job_data.get('posted_date') or job_data.get('posted_date', '').lower() == "unknown":
        age_note = "\n⚠️ *Note:* Posting date not available"
    
    message = (
        f"💼 *{job_data['title']}* {remote_badge}\n"
        f"🏢 *Company:* {job_data['company']}\n"
        f"📍 *Location:* {job_data['location']}\n"
        f" *Salary:* {job_data['salary']}\n"
        f"📅 *Posted:* {job_data.get('posted_date', 'Unknown')}\n"
        f"🎯 *Match Score:* {job_data['match_score']}%\n\n"
        f"📝 *Summary:* {job_data['description']}\n\n"
        f"🔗 *Apply Here:* {job_data['link']}"
        f"{age_note}"
    )
    
    try:
        await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message, parse_mode='Markdown')
        print(f"✅ Sent to Telegram: {job_data['title']}")
    except Exception as e:
        print(f"Telegram Error: {e}")

async def test_telegram():
    """Send a test message to verify Telegram is working"""
    bot = Bot(token=TELEGRAM_BOT_TOKEN)
    try:
        await bot.send_message(
            chat_id=TELEGRAM_CHAT_ID,
            text="✅ **TEST SUCCESSFUL!** Your Job Bot is working!\n\n📋 Filters active:\n• Roles: Operations/Program/CX Management\n• Location: Cairo/Egypt OR Remote\n• Max age: 14 days",
            parse_mode='Markdown'
        )
        print("✅ Telegram test message sent!")
        return True
    except Exception as e:
        print(f"❌ Telegram test failed: {e}")
        return False

# ==========================================
# 4. WEB SCRAPER (LinkedIn & Indeed)
# ==========================================
async def scrape_linkedin_jobs():
    """Scrape LinkedIn Jobs for Operations/Program Management roles"""
    print("🔍 Scraping LinkedIn Jobs...")
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080}
        )
        page = await context.new_page()
        
        # LinkedIn search for Operations/Program Manager in Egypt + Remote
        # Search in Egypt location but also include remote
        url = f"https://www.linkedin.com/jobs/search/?keywords={SEARCH_KEYWORDS.replace(' ', '%20')}&location=Egypt&f_WT=1,2,3&sortBy=DD"
        # f_WT=1,2,3 means: On-site, Hybrid, AND Remote
        # sortBy=DD means "Most recent"
        
        try:
            await page.goto(url, timeout=60000, wait_until="domcontentloaded")
            await page.wait_for_selector("div.job-search-card", timeout=15000)
            
            job_cards = await page.query_selector_all("div.job-search-card")
            print(f"✅ Found {len(job_cards)} LinkedIn jobs!")
            
            jobs_sent = 0
            jobs_filtered = 0
            
            for i, card in enumerate(job_cards[:20]):
                print(f"  Analyzing job {i+1}/{min(20, len(job_cards))}...")
                
                try:
                    raw_text = await card.inner_text()
                    link_elem = await card.query_selector("a")
                    job_link = await link_elem.get_attribute("href") if link_elem else ""
                    
                    if job_link and not job_link.startswith("http"):
                        job_link = f"https://www.linkedin.com{job_link}"
                    
                    raw_text += f"\nLink: {job_link}"
                    
                    job_data = analyze_job_with_ai(raw_text)
                    
                    if not job_data:
                        continue
                    
                    # FILTERS:
                    # 1. Must be valid location (Egypt/Cairo/Remote/MENA)
                    if not job_data.get('is_valid_location', False):
                        print(f"    ❌ Filtered: Invalid location ({job_data.get('location', 'Unknown')})")
                        jobs_filtered += 1
                        continue
                    
                    # 2. Must be recent
                    if not is_job_recent(job_data.get('posted_date', '')):
                        print(f"    ❌ Filtered: Too old ({job_data.get('posted_date', 'Unknown')})")
                        jobs_filtered += 1
                        continue
                    
                    # 3. Match score >= 50
                    if job_data.get("match_score", 0) < 50:
                        print(f"    ❌ Filtered: Low match ({job_data.get('match_score')}%)")
                        jobs_filtered += 1
                        continue
                    
                    await send_job_to_telegram(job_data)
                    jobs_sent += 1
                    
                except Exception as e:
                    print(f"    ⚠️ Error: {e}")
                    continue
            
            print(f"✅ LinkedIn complete. Sent: {jobs_sent}, Filtered: {jobs_filtered}")
            await browser.close()
            return jobs_sent
            
        except Exception as e:
            print(f"❌ LinkedIn failed: {e}")
            await browser.close()
            return 0

async def scrape_indeed_jobs():
    """Scrape Indeed Egypt for Operations/Management roles"""
    print("🔍 Scraping Indeed Egypt...")
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080}
        )
        page = await context.new_page()
        
        # Indeed Egypt - Cairo + Remote, last 14 days
        url = f"https://eg.indeed.com/jobs?q={SEARCH_KEYWORDS.replace(' ', '%20')}&l=Cairo&fromage=14&sort=date"
        
        try:
            await page.goto(url, timeout=60000, wait_until="domcontentloaded")
            await page.wait_for_selector("div.job_seen_beacon", timeout=15000)
            
            job_cards = await page.query_selector_all("div.job_seen_beacon")
            print(f"✅ Found {len(job_cards)} Indeed jobs!")
            
            jobs_sent = 0
            jobs_filtered = 0
            
            for i, card in enumerate(job_cards[:20]):
                print(f"  Analyzing job {i+1}/{min(20, len(job_cards))}...")
                
                try:
                    raw_text = await card.inner_text()
                    link_elem = await card.query_selector("a.jcs-JobTitle")
                    job_link = await link_elem.get_attribute("href") if link_elem else ""
                    
                    if job_link and not job_link.startswith("http"):
                        job_link = f"https://eg.indeed.com{job_link}"
                    
                    raw_text += f"\nLink: {job_link}"
                    
                    job_data = analyze_job_with_ai(raw_text)
                    
                    if not job_data:
                        continue
                    
                    if not job_data.get('is_valid_location', False):
                        print(f"    ❌ Filtered: Invalid location ({job_data.get('location', 'Unknown')})")
                        jobs_filtered += 1
                        continue
                    
                    if not is_job_recent(job_data.get('posted_date', '')):
                        print(f"    ❌ Filtered: Too old ({job_data.get('posted_date', 'Unknown')})")
                        jobs_filtered += 1
                        continue
                    
                    if job_data.get("match_score", 0) < 50:
                        print(f"    ❌ Filtered: Low match ({job_data.get('match_score')}%)")
                        jobs_filtered += 1
                        continue
                    
                    await send_job_to_telegram(job_data)
                    jobs_sent += 1
                    
                except Exception as e:
                    print(f"    ⚠️ Error: {e}")
                    continue
            
            print(f"✅ Indeed complete. Sent: {jobs_sent}, Filtered: {jobs_filtered}")
            await browser.close()
            return jobs_sent
            
        except Exception as e:
            print(f"❌ Indeed failed: {e}")
            await browser.close()
            return 0

# ==========================================
# 5. MAIN EXECUTION
# ==========================================
async def main():
    print("🤖 AI Job Agent is starting in the cloud...")
    print(f" Target roles: Operations/Program/CX Management")
    print(f"📍 Location: Cairo/Egypt OR Remote")
    print(f"📅 Max job age: {MAX_JOB_AGE_DAYS} days")
    
    telegram_ok = await test_telegram()
    if not telegram_ok:
        print("❌ Stopping: Telegram not working")
        return
    
    linkedin_jobs = await scrape_linkedin_jobs()
    
    if linkedin_jobs == 0:
        print("⚠️ Trying Indeed...")
        await asyncio.sleep(5)
        indeed_jobs = await scrape_indeed_jobs()
        
        if indeed_jobs == 0:
            print("⚠️ No matching jobs found. Try adjusting keywords.")
    else:
        print(f"🎉 Successfully sent {linkedin_jobs} jobs!")

if __name__ == "__main__":
    asyncio.run(main())
