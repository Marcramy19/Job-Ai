import asyncio
import json
import os
from playwright.async_api import async_playwright
from telegram import Bot
from groq import Groq

# ==========================================
# 1. CONFIGURATION (Reads from GitHub Secrets)
# ==========================================
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")

# Your CV / Requirements
MY_CV = """
Senior Python Developer with 4 years of experience. 
Skills: Python, Django, FastAPI, React, PostgreSQL, Docker, AWS.
Looking for remote or hybrid roles in Cairo. 
Expected salary: 30,000+ EGP.
"""

SEARCH_KEYWORDS = "Python Django"
LOCATION = "Cairo"

# ==========================================
# 2. AI MATCHING LOGIC (Using Free Groq API)
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
            model="llama-3.3-70b-versatile", # Free, powerful model
            messages=[{"role": "user", "content": prompt}],
            response_format={ "type": "json_object" },
            temperature=0.1
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        print(f"AI Error: {e}")
        return None

# ==========================================
# 3. TELEGRAM NOTIFICATION LOGIC
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

# ==========================================
# 4. WEB SCRAPER LOGIC
# ==========================================
async def scrape_and_filter_jobs():
    print(f"🔍 Starting search for '{SEARCH_KEYWORDS}' in {LOCATION}...")
    
    async with async_playwright() as p:
        # headless=True is REQUIRED for cloud servers
        browser = await p.chromium.launch(headless=True) 
        page = await browser.new_page()
        
        url = f"https://wuzzuf.net/search/jobs?q={SEARCH_KEYWORDS.replace(' ', '%20')}&locations[0]=eg-cairo"
        await page.goto(url, timeout=60000)
        
        try:
            await page.wait_for_selector("div.job-card", timeout=15000)
        except:
            print("❌ Could not find job cards. Wuzzuf might be blocking the cloud IP.")
            await browser.close()
            return

        job_cards = await page.query_selector_all("div.job-card")
        print(f"Found {len(job_cards)} raw job cards. Analyzing with AI...")
        
        for card in job_cards:
            raw_text = await card.inner_text()
            link_element = await card.query_selector("a")
            job_link = await link_element.get_attribute("href") if link_element else "N/A"
            raw_text += f"\nLink: {job_link}"
            
            job_data = analyze_job_with_ai(raw_text)
            
            if job_data and job_data.get("match_score", 0) >= 75:
                await send_job_to_telegram(job_data)
                
        await browser.close()
        print("✅ Scraping complete.")

async def main():
    print("🤖 AI Job Agent is starting in the cloud...")
    await scrape_and_filter_jobs()

if __name__ == "__main__":
    asyncio.run(main())
