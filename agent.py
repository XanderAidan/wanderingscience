import os
import requests
import sys
import json

# --- CONFIGURATION ---
NEWS_API_KEY = os.getenv("NEWS_API_KEY") 
LLM_API_KEY = os.getenv("LLM_API_KEY")   
WP_USER = os.getenv("WP_USER")
WP_PASSWORD = os.getenv("WP_PASSWORD")
WORDPRESS_URL = "https://www.wanderingscience.com/wp-json/wp/v2/posts"

# --- 1. PRE-FLIGHT CHECK ---
if not all([NEWS_API_KEY, LLM_API_KEY, WP_USER, WP_PASSWORD]):
    print("❌ ERROR: Missing API Keys. Check your GitHub Secrets.")
    sys.exit(1)

# --- 2. THE SCOUT (NewsAPI) ---
def fetch_science_news():
    print("🕵️ Scouting for stories...")
    # Broadened search terms slightly
    url = f"https://newsapi.org/v2/everything?q=(biology OR astronomy OR geology OR ecology OR neuroscience OR 'climate change')&domains=nature.com,scientificamerican.com,sciencenews.org,nationalgeographic.com,phys.org&sortBy=publishedAt&language=en&apiKey={NEWS_API_KEY}"
    
    try:
        response = requests.get(url)
        data = response.json()
        
        if data.get('status') == 'ok' and data.get('articles'):
            print(f"✅ Found {len(data['articles'])} articles.")
            return data['articles'][:3]
        else:
            print(f"⚠️ NewsAPI Issue: {data}")
            return None
    except Exception as e:
        print(f"❌ NewsAPI Connection Error: {e}")
        return None

# --- 3. THE CRITIC & WRITER (Now using Google Gemini) ---
def generate_article(articles):
    print("✍️ Writing the article with Gemini...")
    story = articles[0]
    title = story['title']
    description = story['description']
    source = story['source']['name']
    
    # BACKUP CONTENT (Safety net)
    backup_content = f"""
    <!-- BACKUP CONTENT -->
    <p><strong>(Note: Automated verification post.)</strong></p>
    <p>The recent report from {source} regarding <strong>{title}</strong> is a fascinating confirmation of modern theory.</p>
    <p>The implications are significant. Usually, when we look at these datasets, we see noise. But here, the signal is clear.</p>
    <h3>The Travel Angle</h3>
    <p>For those of us who pack bags and head into the field, this changes where we might look next.</p>
    """

    # Gemini Prompt Structure
    system_instruction = """
    You are a seasoned science travel writer for 'Wandering Science'. 
    Your style is SKEPTICAL BUT WONDROUS. 
    NO AI CLICHÉS (delve, tapestry, testament). 
    Write a blog post with a catchy title, 500 words, HTML formatting (<p>, <h3>), and a 'Travel Angle' section.
    """
    
    user_message = f"Write a blog post about: {title}. Context: {description}. Source: {source}."

    # Gemini API Endpoint (Gemini 1.5 Flash is fast and free-tier eligible)
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={LLM_API_KEY}"
    
    headers = { "Content-Type": "application/json" }
    
    # Gemini JSON Payload
    payload = {
        "contents": [{
            "parts": [{"text": system_instruction + "\n\n" + user_message}]
        }]
    }

    try:
        response = requests.post(url, headers=headers, json=payload)
        data = response.json()

        # Check for specific Gemini errors
        if 'error' in data:
            print(f"⚠️ Gemini API Error: {data['error']['message']}")
            return f"Backup Analysis: {title}", backup_content

        # Parse Gemini Response
        if 'candidates' in data and data['candidates']:
            raw_text = data['candidates'][0]['content']['parts'][0]['text']
            # Clean markdown code blocks just in case
            clean_text = raw_text.replace("```html", "").replace("```", "")
            return f"Analysis: {title}", clean_text
        else:
            print(f"⚠️ Unexpected Gemini Response: {data}")
            return f"Backup Analysis: {title}", backup_content

    except Exception as e:
        print(f"❌ Gemini Connection Error: {e}")
        return f"Backup Analysis: {title}", backup_content

# --- 4. THE PUBLISHER (WordPress) ---
def post_to_wordpress(title, content):
    if not title: return

    print("🚀 Publishing to Wandering Science...")
    headers = { "Content-Type": "application/json" }
    post_data = {
        "title": title,
        "content": content,
        "status": "publish", 
        "categories": [2] 
    }

    try:
        r = requests.post(WORDPRESS_URL, auth=(WP_USER, WP_PASSWORD), json=post_data, headers=headers)
        
        if r.status_code in [200, 201]:
            response_json = r.json()
            if isinstance(response_json, list):
                print(f"❌ ERROR: Redirected to GET. Check URL: {WORDPRESS_URL}")
            elif isinstance(response_json, dict) and 'id' in response_json:
                print(f"✅ SUCCESS! Post Created.")
                print(f"   🔗 Link: {response_json.get('link')}")
            else:
                print(f"⚠️ Unexpected Response: {response_json}")
        else:
            print(f"❌ WordPress Upload Failed: {r.status_code} - {r.text}")
            
    except Exception as e:
        print(f"❌ WordPress Connection Error: {e}")

# --- MAIN EXECUTION ---
if __name__ == "__main__":
    news = fetch_science_news()
    if news:
        title, article_html = generate_article(news)
        post_to_wordpress(title, article_html)
    else:
        print("🏁 No news found.")
