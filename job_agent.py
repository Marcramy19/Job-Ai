import asyncio
import json
import os
import random
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
LOCATION = "Cairo"

# ==========================================
# 2. AI MATCHING (Groq Free API)
# ==========================================
groq_client = Groq(api_key=GROQ_API_KEY)

def analyze_job_with_ai(job_raw_text):
    prompt = f"""
    You are an expert technical recruiter. 
    Here is my CV/Profile: {MY_CV}
    Here is the raw text of a job posting: {job_raw_text}

    Analyze the job and return a JSON object with:
    - "title": Job title
    - "company": Company name
    - "location": Job location
    - "salary": Salary if mentioned, otherwise "Not stated"
    - "description": A brief 2-3 sentence summary
    - "link": The URL to apply
    - "match_score": Integer 0-100 for CV match
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

# ==========================================
# 3. TELEGRAM NOTIFICATION
# ==========================================
async def send_job_to_telegram(job_data):
    bot = Bot(token=TELEGRAM_BOT_TOKEN)
    message = (
        f"💼 *{job_data['title']}*\n"
        f"🏢 *Company:* {job_data['company']}\n"
        f"📍 *Location:* {job_data['location']}\n"
        f"💰 *Salary:* {job_data['salary']}\n"
        f"🎯 *Match Score:* {job_data['match_score']}%\n\n"
        f"📝 *Summary:* {job_data['description']}\n\n"
        f"🔗 *Apply Here:* {job_data['link']}"
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
            text="✅ **TEST SUCCESSFUL!** Your Job Bot is working!",
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
        
        # LinkedIn search URL for Python Django jobs in Cairo
        url = f"https://www.linkedin.com/jobs/search/?keywords={SEARCH_KEYWORDS.replace(' ', '%20')}&location=Cairo%2C%20Egypt&geoId=101165590"
        
        try:
            await page.goto(url, timeout=60000, wait_until="domcontentloaded")
            await page.wait_for_selector("div.job-search-card", timeout=15000)
            
            job_cards = await page.query_selector_all("div.job-search-card")
            print(f"✅ Found {len(job_cards)} LinkedIn jobs!")
            
            jobs_sent = 0
            for i, card in enumerate(job_cards[:10]):  # Limit to first 10 jobs
                print(f"  Analyzing job {i+1}/{min(10, len(job_cards))}...")
                
                try:
                    raw_text = await card.inner_text()
                    link_elem = await card.query_selector("a")
                    job_link = await link_elem.get_attribute("href") if link_elem else ""
                    
                    if job_link and not job_link.startswith("http"):
                        job_link = f"https://www.linkedin.com{job_link}"
                    
                    raw_text += f"\nLink: {job_link}"
                    
                    job_data = analyze_job_with_ai(raw_text)
                    
                    if job_data and job_data.get("match_score", 0) >= 50:
                        await send_job_to_telegram(job_data)
                        jobs_sent += 1
                except Exception as e:
                    print(f"    ⚠️ Error processing job: {e}")
                    continue
                    
            print(f"✅ LinkedIn scraping complete. Sent {jobs_sent} jobs.")
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
        
        # Indeed Egypt search URL
        url = f"https://eg.indeed.com/jobs?q={SEARCH_KEYWORDS.replace(' ', '%20')}&l=Cairo"
        
        try:
            await page.goto(url, timeout=60000, wait_until="domcontentloaded")
            await page.wait_for_selector("div.job_seen_beacon", timeout=15000)
            
            job_cards = await page.query_selector_all("div.job_seen_beacon")
            print(f"✅ Found {len(job_cards)} Indeed jobs!")
            
            jobs_sent = 0
            for i, card in enumerate(job_cards[:10]):
                print(f"  Analyzing job {i+1}/{min(10, len(job_cards))}...")
                
                try:
                    raw_text = await card.inner_text()
                    link_elem = await card.query_selector("a.jcs-JobTitle")
                    job_link = await link_elem.get_attribute("href") if link_elem else ""
                    
                    if job_link and not job_link.startswith("http"):
                        job_link = f"https://eg.indeed.com{job_link}"
                    
                    raw_text += f"\nLink: {job_link}"
                    
                    job_data = analyze_job_with_ai(raw_text)
                    
                    if job_data and job_data.get("match_score", 0) >= 50:
                        await send_job_to_telegram(job_data)
                        jobs_sent += 1
                except Exception as e:
                    print(f"    ⚠️ Error processing job: {e}")
                    continue
                    
            print(f"✅ Indeed scraping complete. Sent {jobs_sent} jobs.")
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
    print("🤖 AI Job Agent is starting in the cloud...")
    
    # Test Telegram first
    telegram_ok = await test_telegram()
    if not telegram_ok:
        print("❌ Stopping: Telegram is not working. Check your BOT_TOKEN and CHAT_ID.")
        return
    
    # Try LinkedIn first, then Indeed as fallback
    linkedin_jobs = await scrape_linkedin_jobs()
    
    if linkedin_jobs == 0:
        print("⚠️ No LinkedIn jobs found or error occurred. Trying Indeed...")
        await asyncio.sleep(5)  # Wait a bit before trying another site
        indeed_jobs = await scrape_indeed_jobs()
        
        if indeed_jobs == 0:
            print("⚠️ No jobs found on either platform. This could mean:")
            print("   - No jobs match your criteria")
            print("   - Both sites are blocking GitHub IPs")
            print("   - You need to adjust your search keywords")
    else:
        print(f"🎉 Successfully found and sent {linkedin_jobs} jobs!")

if __name__ == "__main__":
    asyncio.run(main())
