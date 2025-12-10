import os
import requests
import sys
import json
import time

# --- CONFIGURATION ---
NEWS_API_KEY = os.getenv("NEWS_API_KEY") 
LLM_API_KEY = os.getenv("LLM_API_KEY")   
WP_USER = os.getenv("WP_USER")
WP_PASSWORD = os.getenv("WP_PASSWORD")
WORDPRESS_URL = "https://www.wanderingscience.com/wp-json/wp/v2"

# --- 1. PRE-FLIGHT CHECK ---
if not all([NEWS_API_KEY, LLM_API_KEY, WP_USER, WP_PASSWORD]):
    print("❌ ERROR: Missing API Keys. Check your GitHub Secrets.")
    sys.exit(1)

# --- 2. THE SCOUT (NewsAPI) ---
def fetch_science_news():
    print("🕵️ Scouting for stories...")
    # Look for stories with images
    url = f"https://newsapi.org/v2/everything?q=(biology OR astronomy OR geology OR ecology OR neuroscience OR 'climate change')&domains=nature.com,scientificamerican.com,sciencenews.org,nationalgeographic.com,phys.org,smithsonianmag.com&sortBy=publishedAt&language=en&apiKey={NEWS_API_KEY}"
    
    try:
        response = requests.get(url)
        data = response.json()
        
        if data.get('status') == 'ok' and data.get('articles'):
            # Filter for articles that definitely have images
            valid_articles = [a for a in data['articles'] if a.get('urlToImage')]
            print(f"✅ Found {len(valid_articles)} valid articles with images.")
            return valid_articles[:1] 
        else:
            print(f"⚠️ NewsAPI Issue: {data}")
            return None
    except Exception as e:
        print(f"❌ NewsAPI Connection Error: {e}")
        return None

# --- NEW: MODEL AUTO-DISCOVERY ---
def find_best_gemini_model():
    print("🔍 Auto-detecting available Gemini models...")
    list_url = f"https://generativelanguage.googleapis.com/v1beta/models?key={LLM_API_KEY}"
    
    try:
        response = requests.get(list_url)
        data = response.json()
        
        if 'models' not in data:
            print(f"⚠️ Could not list models. Response: {data}")
            return "models/gemini-1.5-flash" # Blind fallback
            
        # Filter for models that support generating content
        available_models = [
            m['name'] for m in data['models'] 
            if 'generateContent' in m.get('supportedGenerationMethods', [])
        ]
        
        # Priority list (Try to find the best one first)
        preferences = [
            "models/gemini-1.5-flash",
            "models/gemini-1.5-pro",
            "models/gemini-1.0-pro",
            "models/gemini-pro"
        ]
        
        # 1. Try to match our preferences exactly
        for pref in preferences:
            if pref in available_models:
                print(f"✅ Selected Optimized Model: {pref}")
                return pref
                
        # 2. If no preference found, take the first available 'gemini' model
        for model in available_models:
            if "gemini" in model:
                print(f"⚠️ Preferred model missing. Using available: {model}")
                return model
                
        print("❌ No valid Gemini models found for this key.")
        return None

    except Exception as e:
        print(f"❌ Model Discovery Error: {e}")
        return "models/gemini-1.5-flash"

# --- 3. THE CRITIC & WRITER ---
def generate_article(article):
    print("✍️ Writing the deep-dive feature...")
    
    title = article['title']
    description = article['description']
    source = article['source']['name']
    url = article['url']
    image_url = article['urlToImage']
    
    # 1. Get the correct model name dynamically
    model_name = find_best_gemini_model()
    if not model_name:
        return None, None

    # RICH CONTENT PROMPT
    system_instruction = """
    You are a senior science editor for 'Wandering Science'. 
    
    MANDATE:
    1. LENGTH: Write a 1,200+ word feature article.
    2. TONE: Engaging, narrative, high-quality journalism (think 'The Atlantic' or 'NatGeo'). 
    3. NO AI CLICHÉS: Do not use "delve", "testament", "tapestry", "in conclusion".
    4. STRUCTURE:
       - <h2>Catchy Section Headers</h2>
       - <blockquote>Pull quotes for emphasis</blockquote>
       - <p>Long, flowing paragraphs.</p>
    5. IMAGERY PLACEMENT: You cannot upload new images, but you MUST indicate where they should go by writing: 
       <div class="image-placeholder"><em>[Suggested Image: Description of what would fit here]</em></div>
    6. CITATIONS: Cite the source ({source}) naturally in the text.
    7. TRAVEL ANGLE: Conclude with a section on where a traveler can go to experience this science.
    """
    
    user_message = f"""
    TOPIC: {title}
    CONTEXT: {description}
    ORIGINAL SOURCE: {source} ({url})
    
    Write the definitive article on this topic now.
    """

    # 2. Construct URL using the auto-discovered name
    # Note: model_name usually comes back as 'models/gemini-1.5-flash', so we append it directly
    api_url = f"https://generativelanguage.googleapis.com/v1beta/{model_name}:generateContent?key={LLM_API_KEY}"
    
    headers = { "Content-Type": "application/json" }
    payload = {
        "contents": [{
            "parts": [{"text": system_instruction + "\n\n" + user_message}]
        }]
    }

    try:
        response = requests.post(api_url, headers=headers, json=payload)
        data = response.json()

        if 'candidates' in data and data['candidates']:
            raw_text = data['candidates'][0]['content']['parts'][0]['text']
            clean_text = raw_text.replace("```html", "").replace("```", "")
            return f"{title}", clean_text
        
        if 'error' in data:
            print(f"❌ Generation Failed: {data['error']['message']}")
            return None, None

    except Exception as e:
        print(f"❌ Connection Error: {e}")
        return None, None
    
    return None, None

# --- 4. MEDIA UPLOADER ---
def upload_image_to_wordpress(image_url, title):
    if not image_url: return None
    
    print(f"🖼️ Uploading Featured Image: {image_url}...")
    
    try:
        img_response = requests.get(image_url)
        if img_response.status_code != 200:
            print("   ⚠️ Could not download image.")
            return None
            
        filename = f"science-news-{title[:10].replace(' ', '-').lower()}.jpg"
        
        media_url = f"{WORDPRESS_URL}/media"
        headers = {
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Type": "image/jpeg"
        }
        
        r = requests.post(media_url, auth=(WP_USER, WP_PASSWORD), headers=headers, data=img_response.content)
        
        if r.status_code == 201:
            media_id = r.json().get('id')
            print(f"   ✅ Image uploaded successfully (ID: {media_id})")
            return media_id
        else:
            print(f"   ❌ WP Media Upload Failed: {r.text}")
            return None
            
    except Exception as e:
        print(f"   ❌ Image Upload Error: {e}")
        return None

# --- 5. THE PUBLISHER ---
def post_to_wordpress(title, content, featured_media_id=None):
    if not title or not content: return

    print("🚀 Publishing Article...")
    headers = { "Content-Type": "application/json" }
    
    post_data = {
        "title": title,
        "content": content,
        "status": "publish", 
        "categories": [2],
        "featured_media": featured_media_id
    }

    try:
        r = requests.post(f"{WORDPRESS_URL}/posts", auth=(WP_USER, WP_PASSWORD), json=post_data, headers=headers)
        
        if r.status_code in [200, 201]:
            print(f"✅ SUCCESS! Post is live.")
            print(f"   🔗 Link: {r.json().get('link')}")
        else:
            print(f"❌ WordPress Upload Failed: {r.status_code} - {r.text}")
            
    except Exception as e:
        print(f"❌ WordPress Connection Error: {e}")

# --- MAIN EXECUTION ---
if __name__ == "__main__":
    articles = fetch_science_news()
    if articles:
        article = articles[0]
        title, article_html = generate_article(article)
        
        if title and article_html:
            media_id = upload_image_to_wordpress(article.get('urlToImage'), title)
            post_to_wordpress(title, article_html, media_id)
        else:
            print("⚠️ Content generation failed.")
    else:
        print("🏁 No news found.")
