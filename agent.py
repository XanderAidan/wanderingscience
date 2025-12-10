import os
import requests
import sys

# --- CONFIGURATION ---
NEWS_API_KEY = os.getenv("NEWS_API_KEY") 
LLM_API_KEY = os.getenv("LLM_API_KEY")   
WP_USER = os.getenv("WP_USER")
WP_PASSWORD = os.getenv("WP_PASSWORD")
WORDPRESS_URL = "https://wanderingscience.com/wp-json/wp/v2/posts"

# --- 1. PRE-FLIGHT CHECK ---
# This ensures we don't run blindly without keys
if not all([NEWS_API_KEY, LLM_API_KEY, WP_USER, WP_PASSWORD]):
    print("❌ ERROR: Missing API Keys in Environment.")
    print("   Make sure you have set these in GitHub Secrets AND mapped them in the workflow YAML.")
    sys.exit(1)

# --- 2. THE SCOUT ---
def fetch_science_news():
    print("🕵️ Scouting for stories...")
    url = f"https://newsapi.org/v2/everything?q=(biology OR astronomy OR geology OR ecology OR neuroscience OR 'climate change')&domains=nature.com,scientificamerican.com,sciencenews.org,nationalgeographic.com&sortBy=publishedAt&language=en&apiKey={NEWS_API_KEY}"
    
    try:
        response = requests.get(url)
        data = response.json()
        
        if data.get('status') == 'ok' and data.get('articles'):
            print(f"✅ Found {len(data['articles'])} articles.")
            return data['articles'][:3]
        else:
            print(f"⚠️ NewsAPI Output: {data}")
            return None
    except Exception as e:
        print(f"❌ NewsAPI Connection Error: {e}")
        return None

# --- 3. THE CRITIC & WRITER ---
def generate_article(articles):
    print("✍️ Writing the article...")
    story = articles[0]
    title = story['title']
    description = story['description']
    source = story['source']['name']
    
    system_prompt = "You are a seasoned science travel writer for 'Wandering Science'. Your style is SKEPTICAL BUT WONDROUS. No AI cliches. Write a blog post with a catchy title, 500 words, and a 'Travel Angle' section."
    user_prompt = f"Write a blog post about: {title}. Context: {description}. Source: {source}."

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {LLM_API_KEY}"
    }
    
    # Using GPT-4o or Turbo
    payload = {
        "model": "gpt-4-turbo", 
        "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
        "temperature": 0.7 
    }

    try:
        response = requests.post("https://api.openai.com/v1/chat/completions", json=payload, headers=headers)
        data = response.json()

        if 'choices' in data:
            content = data['choices'][0]['message']['content']
            # Clean markdown code fences if present
            content = content.replace("```html", "").replace("```", "")
            return f"Analysis: {title}", content
        else:
            print(f"⚠️ AI Error: {data}")
            return None, None
    except Exception as e:
        print(f"❌ AI Connection Error: {e}")
        return None, None

# --- 4. THE PUBLISHER ---
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
        # FIX: Ensure this block is indented correctly
        r = requests.post(WORDPRESS_URL, auth=(WP_USER, WP_PASSWORD), json=post_data, headers=headers)
        
        if r.status_code == 201:
            print(f"✅ SUCCESS! Post is live: {title}")
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
        print("🏁 No news found or generation failed.")
