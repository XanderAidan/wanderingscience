import os
import requests
import sys
import json
import time
import random

# --- CONFIGURATION (Uses your existing secrets) ---
NEWS_API_KEY = os.getenv("NEWS_API_KEY") 
LLM_API_KEY = os.getenv("LLM_API_KEY")   
WP_USER = os.getenv("WP_USER")
WP_PASSWORD = os.getenv("WP_PASSWORD")
# Enforcing the 'www' to prevent redirect errors
WORDPRESS_URL = "https://www.wanderingscience.com/wp-json/wp/v2"

# --- SAFETY CHECKS ---
if not all([NEWS_API_KEY, LLM_API_KEY, WP_USER, WP_PASSWORD]):
    print("❌ CRITICAL: Missing API Keys. Script cannot run.")
    sys.exit(1)

# --- HELPER: BROWSER HEADERS ---
def get_browser_headers():
    return {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }

# --- NEW HELPER: DUPLICATE CHECKER ---
def check_if_post_exists(search_term):
    search_url = f"{WORDPRESS_URL}/posts"
    params = { "search": search_term, "per_page": 1 }
    try:
        response = requests.get(search_url, params=params, headers=get_browser_headers(), timeout=10)
        if response.status_code == 200 and len(response.json()) > 0:
            return True
    except Exception as e:
        print(f"   ⚠️ Search check failed: {e}")
    return False

# --- PHASE 1: THE SCOUT (General Science) ---
def fetch_top_science_story():
    print("🔭 Scouting for a General Science story...")
    
    # Broad Science Query
    query = "(astronomy OR geology OR biology OR neuroscience OR 'climate change' OR archaeology OR physics)"
    domains = "nature.com,scientificamerican.com,sciencenews.org,nationalgeographic.com,smithsonianmag.com,phys.org,theguardian.com,bbc.com"
    
    url = f"https://newsapi.org/v2/everything?q={query}&domains={domains}&sortBy=publishedAt&language=en&apiKey={NEWS_API_KEY}"
    
    try:
        response = requests.get(url, headers=get_browser_headers())
        data = response.json()
        
        if data.get('status') == 'ok' and data.get('articles'):
            # Filter: Must have an image, must not be removed
            valid_articles = [
                a for a in data['articles'] 
                if a.get('urlToImage') and "removed" not in a['title'].lower()
            ]
            
            if valid_articles:
                print(f"✅ Found {len(valid_articles)} candidates. Checking for duplicates...")
                for article in valid_articles:
                    if not check_if_post_exists(article['title']):
                        print(f"   ✨ Selected fresh story: {article['title']}")
                        return article
                    else:
                        print(f"   ⏩ Skipping duplicate: {article['title']}")
                print("⚠️ All candidates were duplicates.")
                return None
            else:
                print("⚠️ Found articles, but none had valid images.")
                return None
        else:
            print(f"⚠️ NewsAPI Response: {data}")
            return None
            
    except Exception as e:
        print(f"❌ Network Error (NewsAPI): {e}")
        return None

# --- PHASE 2: MEDIA MANAGER ---
def upload_image_to_wordpress(image_url, title):
    if not image_url: return None, None
    print(f"🖼️ Processing Image: {image_url}...")
    try:
        img_response = requests.get(image_url, headers=get_browser_headers(), timeout=15)
        if img_response.status_code != 200: return None, None
            
        clean_title = "".join(c for c in title if c.isalnum() or c in (' ','-')).rstrip()
        filename = f"science-{clean_title[:20].replace(' ', '-').lower()}.jpg"
        
        api_url = f"{WORDPRESS_URL}/media"
        wp_headers = {
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Type": "image/jpeg",
            "User-Agent": get_browser_headers()["User-Agent"]
        }
        
        r = requests.post(api_url, auth=(WP_USER, WP_PASSWORD), headers=wp_headers, data=img_response.content, timeout=30)
        if r.status_code == 201:
            data = r.json()
            return data.get('id'), data.get('source_url')
        else:
            return None, None
    except Exception:
        return None, None

# --- PHASE 3: THE AUTHOR (Gemini Cascade) ---
def write_feature_article(article, image_url_for_embedding):
    print("✍️ Commissioning article from AI...")
    
    title = article['title']
    desc = article['description']
    source = article['source']['name']
    url = article['url'] 
    
    # PROMPT ENGINEERING (General Science Focus)
    system_instruction = f"""
    You are the Senior Editor for 'Wandering Science'. You bridge the gap between rigorous academic research and the spirit of exploration.
    
    YOUR TASK: Write a long-form feature article (approx. 1200 words) on the provided topic.
    
    CRITICAL FORMATTING RULES:
    1. OUTPUT PURE HTML ONLY. No Markdown (No #, No *). 
    2. MANDATORY IMAGE EMBED: Include this exact HTML tag around paragraph 3:
       <figure class="wp-block-image aligncenter size-large"><img src="{image_url_for_embedding}" alt="Scientific context visualization"/><figcaption>Visual context from {source}.</figcaption></figure>
    
    TONE & STYLE:
    - Intellectual, narrative-driven journalism (think 'The Atlantic' or 'National Geographic').
    - Start with a scene, a question, or a sensory detail. Do not start with "A new study says".
    - NO AI PATTERNS: Do not use "delve", "testament", "tapestry", "unmasking", "in conclusion".
    
    STRUCTURE:
    1. <h1>{title}</h1>
    2. The Narrative Hook (Draw the reader in)
    3. The Hard Science (Explain the mechanism/discovery depth)
    4. The Broader Context (Why this matters to our understanding of the universe/earth)
    5. The Traveler's Perspective (Where can a non-scientist go to witness this? Museums? Field sites?)
    """
    
    user_prompt = f"HEADLINE: {title}\nSUMMARY: {desc}\nSOURCE: {source}\n\nWrite the article now. Start directly with the <h1> tag."

    # Using the latest Flash models as requested
    model_cascade = ["gemini-2.0-flash-exp", "gemini-1.5-flash", "gemini-1.5-flash-8b", "gemini-1.0-pro"]
    
    headers = { "Content-Type": "application/json" }
    payload = {
        "contents": [{"parts": [{"text": system_instruction + "\n\n" + user_prompt}]}],
        "generationConfig": {"temperature": 0.7, "maxOutputTokens": 2000}
    }

    for model in model_cascade:
        print(f"🤖 Attempting generation with model: {model}...")
        api_url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={LLM_API_KEY}"

        try:
            response = requests.post(api_url, headers=headers, json=payload)
            if response.status_code == 429: continue # Rate limit, try next
                
            data = response.json()
            if 'candidates' in data and data['candidates']:
                raw_html = data['candidates'][0]['content']['parts'][0]['text']
                clean_html = raw_html.replace("```html", "").replace("```", "").strip()
                
                # Append Source Link
                source_footer = f"""
                <hr class="wp-block-separator has-alpha-channel-opacity"/>
                <div class="article-source" style="margin-top: 2rem; font-style: italic; color: #555;">
                    <p><strong>Source:</strong> <a href="{url}" target="_blank" rel="noopener noreferrer">Read the original reporting at {source}</a></p>
                </div>
                """
                return title, clean_html + source_footer
            
        except Exception as e:
            continue

    print("❌ All AI models failed.")
    return None, None

# --- PHASE 4: THE PUBLISHER ---
def publish_to_wordpress(title, content, media_id):
    if not content: return
    print("🚀 Publishing to Wandering Science...")
    post_data = {
        "title": title,
        "content": content,
        "status": "publish",
        "categories": [2], 
        "featured_media": media_id
    }
    try:
        headers = { "User-Agent": get_browser_headers()["User-Agent"] }
        r = requests.post(f"{WORDPRESS_URL}/posts", auth=(WP_USER, WP_PASSWORD), json=post_data, headers=headers, timeout=30)
        if r.status_code in [200, 201]: print(f"✅ SUCCESS! Article Live: {r.json().get('link')}")
        else: print(f"❌ Publish Failed: {r.status_code} - {r.text}")
    except Exception as e: print(f"❌ Publish Network Error: {e}")

if __name__ == "__main__":
    article = fetch_top_science_story()
    if article:
        media_id, uploaded_url = upload_image_to_wordpress(article.get('urlToImage'), article['title'])
        img_ref = uploaded_url if uploaded_url else ""
        title, content = write_feature_article(article, img_ref)
        if title and content: publish_to_wordpress(title, content, media_id)
    else:
        print("🏁 No valid stories found today.")
