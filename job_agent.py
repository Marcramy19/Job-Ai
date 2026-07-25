import asyncio
import json
import os
from datetime import datetime, timedelta
from playwright.async_api import async_playwright
from telegram import Bot
from groq import Groq

# ==========================================
# 1. CONFIGURATION
# ==========================================
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")

MY_CV = """
Senior Python Developer with 4 years of experience. 
Skills: Python, Django, FastAPI, React, PostgreSQL, Docker, AWS.
Looking for remote or hybrid roles in Cairo. 
Expected salary: 30,000+ EGP.
"""

SEARCH_KEYWORDS = "Python Django"
MAX_JOB_AGE_DAYS = 7  # Only show jobs posted in the last 7 days

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
    1. Location MUST be in Cairo, Egypt (or fully remote)
    2. Job should be recently posted (extract the posting date if available)
    
    Analyze the job and return a JSON object with:
    - "title": Job title
    - "company": Company name
    - "location": Exact location as stated (must include Cairo/Egypt or Remote)
    - "salary": Salary if mentioned, otherwise "Not stated"
    - "posted_date": The posting date if available (e.g., "2 days ago", "Jan 15, 2026"), otherwise "Unknown"
    - "description": A brief 2-3 sentence summary
    - "link": The URL to apply
    - "match_score": Integer 0-100 for CV match
    - "is_cairo_location": true/false (true ONLY if location is Cairo, Egypt, Giza, Alexandria, or fully Remote)
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
        return True  # If date unknown, include it but flag it
    
    posted_date_str = posted_date_str.lower()
    
    # Handle relative dates like "2 days ago", "1 week ago"
    if "day" in posted_date_str:
        try:
            days_ago = int(''.join(filter(str.isdigit, posted_date_str)))
            return days_ago <= MAX_JOB_AGE_DAYS
        except:
            return True
    
    if "week" in posted_date_str:
        try:
            weeks_ago = int(''.join(filter(str.isdigit, posted_date_str)))
            return weeks_ago == 0  # Only this week
        except:
            return True
    
    if "month" in posted_date_str or "hour" in posted_date_str:
        # If it mentions months, it's too old. Hours are fine.
        return "month" not in posted_date_str
    
    # Try to parse absolute dates (e.g., "Jan 15, 2026")
    try:
        # Common date formats
        for fmt in ["%b %d, %Y", "%B %d, %Y", "%d %b %Y", "%Y-%m-%d"]:
            try:
                posted_date = datetime.strptime(posted_date_str.strip(), fmt)
                age = datetime.now() - posted_date
                return age.days <= MAX_JOB_AGE_DAYS
            except:
                continue
        return True  # If can't parse, include it
    except:
        return True

# ==========================================
# 3. TELEGRAM NOTIFICATION
# ==========================================
async def send_job_to_telegram(job_data):
    bot = Bot(token=TELEGRAM_BOT_TOKEN)
    
    # Add age warning if date is unknown
    age_note = ""
    if not job_data.get('posted_date') or job_data.get('posted_date', '').lower() == "unknown":
        age_note = "\n⚠️ *Note:* Posting date not available"
    
    message = (
        f"💼 *{job_data['title']}*\n"
        f"🏢 *Company:* {job_data['company']}\n"
        f"📍 *Location:* {job_data['location']}\n"
        f"💰 *Salary:* {job_data['salary']}\n"
        f" *Posted:* {job_data.get('posted_date', 'Unknown')}\n"
        f" *Match Score:* {job_data['match_score']}%\n\n"
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
            text="✅ **TEST SUCCESSFUL!** Your Job Bot is working!\n\n📋 Filters active:\n• Location: Cairo/Egypt only\n• Max age: 7 days",
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
    """Scrape LinkedIn Jobs for Cairo"""
    print("🔍 Scraping LinkedIn Jobs...")
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080}
        )
        page = await context.new_page()
        
        # LinkedIn search URL for Python Django jobs in Cairo, Egypt (sorted by date)
        url = f"https://www.linkedin.com/jobs/search/?keywords={SEARCH_KEYWORDS.replace(' ', '%20')}&location=Cairo%2C%20Egypt&geoId=101165590&f_TPR=r604800&sortBy=DD"
        # f_TPR=r604800 means "past week" (604800 seconds = 7 days)
        # sortBy=DD means "Most recent"
        
        try:
            await page.goto(url, timeout=60000, wait_until="domcontentloaded")
            await page.wait_for_selector("div.job-search-card", timeout=15000)
            
            job_cards = await page.query_selector_all("div.job-search-card")
            print(f"✅ Found {len(job_cards)} LinkedIn jobs!")
            
            jobs_sent = 0
            jobs_filtered = 0
            
            for i, card in enumerate(job_cards[:15]):  # Check first 15 jobs
                print(f"  Analyzing job {i+1}/{min(15, len(job_cards))}...")
                
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
                    
                    # STRICT FILTERS:
                    # 1. Must be Cairo/Egypt location
                    if not job_data.get('is_cairo_location', False):
                        print(f"    ❌ Filtered out: Not in Cairo (location: {job_data.get('location', 'Unknown')})")
                        jobs_filtered += 1
                        continue
                    
                    # 2. Must be recent job
                    if not is_job_recent(job_data.get('posted_date', '')):
                        print(f"    ❌ Filtered out: Too old (posted: {job_data.get('posted_date', 'Unknown')})")
                        jobs_filtered += 1
                        continue
                    
                    # 3. Match score must be >= 50
                    if job_data.get("match_score", 0) < 50:
                        print(f"    ❌ Filtered out: Low match score ({job_data.get('match_score')}%)")
                        jobs_filtered += 1
                        continue
                    
                    await send_job_to_telegram(job_data)
                    jobs_sent += 1
                    
                except Exception as e:
                    print(f"    ⚠️ Error processing job: {e}")
                    continue
            
            print(f"✅ LinkedIn scraping complete.")
            print(f"   📤 Sent: {jobs_sent} jobs")
            print(f"   🚫 Filtered: {jobs_filtered} jobs")
            
            await browser.close()
            return jobs_sent
            
        except Exception as e:
            print(f"❌ LinkedIn scraping failed: {e}")
            await browser.close()
            return 0

async def scrape_indeed_jobs():
    """Scrape Indeed Egypt for Cairo jobs"""
    print("🔍 Scraping Indeed Egypt...")
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080}
        )
        page = await context.new_page()
        
        # Indeed Egypt search URL - Cairo only, last 7 days, sorted by date
        url = f"https://eg.indeed.com/jobs?q={SEARCH_KEYWORDS.replace(' ', '%20')}&l=Cairo&fromage=7&sort=date"
        # fromage=7 means "last 7 days"
        # sort=date means "sorted by date"
        
        try:
            await page.goto(url, timeout=60000, wait_until="domcontentloaded")
            await page.wait_for_selector("div.job_seen_beacon", timeout=15000)
            
            job_cards = await page.query_selector_all("div.job_seen_beacon")
            print(f"✅ Found {len(job_cards)} Indeed jobs!")
            
            jobs_sent = 0
            jobs_filtered = 0
            
            for i, card in enumerate(job_cards[:15]):
                print(f"  Analyzing job {i+1}/{min(15, len(job_cards))}...")
                
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
                    
                    # STRICT FILTERS:
                    if not job_data.get('is_cairo_location', False):
                        print(f"    ❌ Filtered out: Not in Cairo (location: {job_data.get('location', 'Unknown')})")
                        jobs_filtered += 1
                        continue
                    
                    if not is_job_recent(job_data.get('posted_date', '')):
                        print(f"    ❌ Filtered out: Too old (posted: {job_data.get('posted_date', 'Unknown')})")
                        jobs_filtered += 1
                        continue
                    
                    if job_data.get("match_score", 0) < 50:
                        print(f"    ❌ Filtered out: Low match score ({job_data.get('match_score')}%)")
                        jobs_filtered += 1
                        continue
                    
                    await send_job_to_telegram(job_data)
                    jobs_sent += 1
                    
                except Exception as e:
                    print(f"    ⚠️ Error processing job: {e}")
                    continue
            
            print(f"✅ Indeed scraping complete.")
            print(f"   📤 Sent: {jobs_sent} jobs")
            print(f"   🚫 Filtered: {jobs_filtered} jobs")
            
            await browser.close()
            return jobs_sent
            
        except Exception as e:
            print(f"❌ Indeed scraping failed: {e}")
            await browser.close()
            return 0

# ==========================================
# 5. MAIN EXECUTION
# ==========================================
async def main():
    print(" AI Job Agent is starting in the cloud...")
    print(f"📍 Location filter: Cairo/Egypt only")
    print(f"📅 Max job age: {MAX_JOB_AGE_DAYS} days")
    
    # Test Telegram first
    telegram_ok = await test_telegram()
    if not telegram_ok:
        print(" Stopping: Telegram is not working. Check your BOT_TOKEN and CHAT_ID.")
        return
    
    # Try LinkedIn first, then Indeed as fallback
    linkedin_jobs = await scrape_linkedin_jobs()
    
    if linkedin_jobs == 0:
        print("⚠️ No LinkedIn jobs found or error occurred. Trying Indeed...")
        await asyncio.sleep(5)
        indeed_jobs = await scrape_indeed_jobs()
        
        if indeed_jobs == 0:
            print("⚠️ No jobs found on either platform that match your filters.")
            print("   Try:")
            print("   - Widening MAX_JOB_AGE_DAYS")
            print("   - Changing SEARCH_KEYWORDS")
            print("   - Checking if sites are blocking GitHub IPs")
    else:
        print(f"🎉 Successfully found and sent {linkedin_jobs} jobs!")

if __name__ == "__main__":
    asyncio.run(main())
