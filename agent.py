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
if not all([NEWS_API_KEY, LLM_API_KEY, WP_USER, WP_PASSWORD]):
    print("❌ ERROR: Missing API Keys in Environment.")
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
    
    # BACKUP CONTENT (Used if AI fails due to quota/errors)
    backup_content = f"""
    <!-- BACKUP CONTENT MODE -->
    <p><strong>(Note: The AI Agent encountered a quota limit, so this is a backup post to verify the pipeline.)</strong></p>
    
    <p>It was only a matter of time before the data caught up with the theory. The recent report from {source} regarding <strong>{title}</strong> is less of a surprise and more of a confirmation of what many field researchers have whispered about for years.</p>
    
    <p>The implications are fascinating. Usually, when we look at these datasets, we see noise. But here, the signal is clear. The team behind the study managed to isolate variables that have plagued previous attempts.</p>
    
    <h3>The Travel Angle</h3>
    <p>For those of us who pack bags and head into the field, this changes where we might look next. If this data holds true, the next great frontier isn't in the remote Amazon, but perhaps in the forgotten archival drawers of our local museums.</p>
    """

    system_prompt = "You are a seasoned science travel writer for 'Wandering Science'. Your style is SKEPTICAL BUT WONDROUS. No AI cliches. Write a blog post with a catchy title, 500 words, and a 'Travel Angle' section."
    user_prompt = f"Write a blog post about: {title}. Context: {description}. Source: {source}."

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {LLM_API_KEY}"
    }
    
    # Payload for OpenAI
    payload = {
        "model": "gpt-3.5-turbo", 
        "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
        "temperature": 0.7 
    }

    try:
        response = requests.post("https://api.openai.com/v1/chat/completions", json=payload, headers=headers)
        data = response.json()

        # ERROR HANDLING: Catch Quota or API errors gracefully
        if 'error' in data:
            print(f"⚠️ OpenAI API Error: {data['error']['message']}")
            print("⚠️ SWITCHING TO BACKUP CONTENT so the workflow finishes.")
            return f"Backup Analysis: {title}", backup_content

        if 'choices' in data:
            content = data['choices'][0]['message']['content']
            content = content.replace("```html", "").replace("```", "")
            return f"Analysis: {title}", content
        else:
            print(f"⚠️ Unknown AI Response: {data}")
            return f"Backup Analysis: {title}", backup_content

    except Exception as e:
        print(f"❌ AI Connection Error: {e}")
        print("⚠️ SWITCHING TO BACKUP CONTENT.")
        return f"Backup Analysis: {title}", backup_content

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
