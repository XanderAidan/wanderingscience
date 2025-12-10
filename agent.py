import os
import requests
import datetime
import random
from datetime import timedelta

# Configuration (These load from your GitHub Secrets / Environment Variables)
NEWS_API_KEY = os.getenv("NEWS_API_KEY") 
LLM_API_KEY = os.getenv("LLM_API_KEY")   
WORDPRESS_URL = "https://wanderingscience.com/wp-json/wp/v2/posts"
WP_USER = os.getenv("WP_USER")
WP_PASSWORD = os.getenv("WP_PASSWORD")   

# 1. THE SCOUT: Find fresh science news
def fetch_science_news():
    print("🕵️ Scouting for stories...")
    # Searching for high-quality domains
    url = f"https://newsapi.org/v2/everything?q=(biology OR astronomy OR geology OR ecology OR neuroscience OR 'climate change')&domains=nature.com,scientificamerican.com,sciencenews.org,nationalgeographic.com&sortBy=publishedAt&language=en&apiKey={NEWS_API_KEY}"
    
    try:
        response = requests.get(url)
        data = response.json()
        
        if data.get('status') == 'ok' and data.get('articles'):
            # Return the top 3 articles
            return data['articles'][:3]
        else:
            print(f"⚠️ NewsAPI Error or No Data: {data}")
            return None
    except Exception as e:
        print(f"❌ Connection Error (NewsAPI): {e}")
        return None

# 2. THE CRITIC & WRITER: Generate the content
def generate_article(articles):
    print("✍️ Writing the article...")
    
    story = articles[0]
    title = story['title']
    description = story['description']
    source = story['source']['name']
    
    # The "Anti-AI" Persona
    system_prompt = """
    You are a seasoned science travel writer for 'Wandering Science'. 
    Your style is:
    - SKEPTICAL BUT WONDROUS: You love science, but you hate hype.
    - NARRATIVE DRIVEN: Start with a scene or a specific detail, not a summary.
    - NO AI CLICHÉS: Do not use the words "delve", "landscape", "testament", "tapestry", or "In conclusion".
    - NO BULLET POINTS: Write in flowing paragraphs only.
    - HUMAN MARKERS: Use phrases like "I suspect," "It brings to mind," or "curiously."
    - STRUCTURE: A catchy title, a 500-word body, and a short 'Travel Angle' at the end (how this relates to seeing the world).
    """

    user_prompt = f"""
    Write a blog post based on this news event:
    Headline: {title}
    Context: {description}
    Source: {source}
    
    Make it sound like it was written by a human sitting in a coffee shop, analyzing the news.
    """

    # --- REAL AI CALL (OpenAI Compatible) ---
    if not LLM_API_KEY:
        print("❌ Error: LLM_API_KEY is missing.")
        return None, None

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {LLM_API_KEY}"
    }

    # Using GPT-4o or GPT-4-turbo for best writing quality
    payload = {
        "model": "gpt-4-turbo", 
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "temperature": 0.7 
    }

    try:
        response = requests.post("https://api.openai.com/v1/chat/completions", json=payload, headers=headers)
        response_data = response.json()

        if 'choices' in response_data:
            content = response_data['choices'][0]['message']['content']
            # Clean up potential markdown formatting wrapping
            content = content.replace("```html", "").replace("```", "")
            return f"Analysis: {title}", content
        else:
            print(f"⚠️ AI API Error: {response_data}")
            return None, None

    except Exception as e:
        print(f"❌ Connection Error (AI): {e}")
        return None, None


# 3. THE PUBLISHER: Post to WordPress
def post_to_wordpress(title, content):
    if not title or not content:
        print("⚠️ Skipping upload: No content generated.")
        return

    print("🚀 Publishing to Wandering Science...")
    
    headers = {
        "Content-Type": "application/json",
    }
    
    post_data = {
        "title": title,
        "content": content,
        "status": "publish", 
        "categories": [2], # Ensure this Category ID exists in your WP
    }

    try:
        r = requests.post(WORDPRESS_URL, auth=(WP_USER, WP_PASSWORD), json=post_data, headers=headers)
        
        if r.status_code == 201:
            print(f"✅ Success! Post '{title}' is live.")
        else:
            print(f"❌ Error {r.status_code}: {r.text}")
            
    except Exception as e:
        print(f"❌ Connection Error (WordPress): {e}")

# Main Execution Flow
if __name__ == "__main__":
    news = fetch_science_news()
    if news:
        title, article_html = generate_article(news)
        post_to_wordpress(title, article_html)
    else:
        print("No significant news found today. Skipping.")
