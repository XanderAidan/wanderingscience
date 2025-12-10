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
# Prevents 403 Forbidden / Connection Timed Out errors from WordPress security plugins
def get_browser_headers():
    return {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }

# --- NEW HELPER: DUPLICATE CHECKER ---
def check_if_post_exists(search_term):
    """
    Queries WordPress to see if a post with this topic already exists.
    Returns True if a matching post is found.
    """
    search_url = f"{WORDPRESS_URL}/posts"
    params = {
        "search": search_term,
        "per_page": 1
    }
    
    try:
        # Use public GET request to search posts
        response = requests.get(search_url, params=params, headers=get_browser_headers(), timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            if len(data) > 0:
                print(f"   (Found existing post ID: {data[0]['id']})")
                return True
    except Exception as e:
        print(f"   ⚠️ Search check failed: {e}")
        
    return False

# --- PHASE 1: THE SCOUT (NewsAPI) ---
def fetch_top_science_story():
    print("🕵️ Scouting for the perfect story...")
    
    query = "(entomology OR neuroscience OR biology OR astronomy OR 'climate change' OR archaeology)"
    domains = "nature.com,scientificamerican.com,sciencenews.org,nationalgeographic.com,smithsonianmag.com,phys.org,theguardian.com"
    
    url = f"https://newsapi.org/v2/everything?q={query}&domains={domains}&sortBy=publishedAt&language=en&apiKey={NEWS_API_KEY}"
    
    try:
        response = requests.get(url, headers=get_browser_headers())
        data = response.json()
        
        if data.get('status') == 'ok' and data.get('articles'):
            valid_articles = [
                a for a in data['articles'] 
                if a.get('urlToImage') and "removed" not in a['title'].lower()
            ]
            
            if valid_articles:
                print(f"✅ Found {len(valid_articles)} candidates. Checking for duplicates...")
                
                # Loop through candidates to find a fresh one
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

# --- PHASE 2: MEDIA MANAGER (Image Handling) ---
def upload_image_to_wordpress(image_url, title):
    """
    Downloads the image from the news source and uploads it to your WP Media Library.
    """
    if not image_url: return None, None
    
    print(f"🖼️ Processing Image: {image_url}...")
    
    try:
        # 1. Download Content (With timeout and headers)
        img_response = requests.get(image_url, headers=get_browser_headers(), timeout=15)
        if img_response.status_code != 200:
            print("   ⚠️ Failed to download source image.")
            return None, None
            
        # 2. Prepare Filename
        clean_title = "".join(c for c in title if c.isalnum() or c in (' ','-')).rstrip()
        filename = f"science-{clean_title[:20].replace(' ', '-').lower()}.jpg"
        
        # 3. Upload to WordPress
        api_url = f"{WORDPRESS_URL}/media"
        # We need specific auth headers for WP, not the browser ones
        wp_headers = {
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Type": "image/jpeg",
            "User-Agent": get_browser_headers()["User-Agent"] # Add UA to WP request too
        }
        
        r = requests.post(api_url, auth=(WP_USER, WP_PASSWORD), headers=wp_headers, data=img_response.content, timeout=30)
        
        if r.status_code == 201:
            data = r.json()
            media_id = data.get('id')
            uploaded_url = data.get('source_url')
            print(f"   ✅ Image uploaded to library (ID: {media_id})")
            return media_id, uploaded_url
        else:
            print(f"   ❌ WP Upload Failed: {r.status_code} - {r.text}")
            return None, None
            
    except Exception as e:
        print(f"   ❌ Image Processing Error: {e}")
        return None, None

# --- PHASE 3: THE AUTHOR (Gemini Cascade) ---
def write_feature_article(article, image_url_for_embedding):
    print("✍️ Commissioning article from AI...")
    
    title = article['title']
    desc = article['description']
    source = article['source']['name']
    url = article['url'] # <--- This captures the original link
    
    # PROMPT ENGINEERING
    system_instruction = f"""
    You are the lead editor for 'Wandering Science', a prestigious journal bridging Entomology, Neuroscience, and Exploration.
    
    YOUR TASK: Write a long-form, magazine-style feature article (approx. 1200 words) on the provided topic.
    
    CRITICAL FORMATTING RULES (STRICT COMPLIANCE REQUIRED):
    1. OUTPUT PURE HTML ONLY. Do NOT use Markdown (No # for headers, No * for bold). 
       - CORRECT: <h1>Title</h1>, <h2>Header</h2>, <strong>Bold</strong>.
       - INCORRECT: # Title, **Bold**.
    2. NO IMAGE PLACEHOLDERS. Do NOT write "[Suggested Image]" or "[Insert Image Here]".
    3. MANDATORY IMAGE EMBED: You MUST include the following HTML tag exactly as written inside the article body (around the 3rd paragraph):
       <figure class="wp-block-image aligncenter size-large"><img src="{image_url_for_embedding}" alt="Visual context for the research"/><figcaption>Visual context from {source}.</figcaption></figure>
    4. MANDATORY SOURCE LINK: You MUST end the article with a specific "Sources" section containing this exact HTML link:
       <p class="source-link"><strong>Source:</strong> <a href="{url}" target="_blank" rel="noopener noreferrer">Read the original reporting at {source}</a></p>
    
    TONE & STYLE:
    - Intellectual but accessible (think 'The Atlantic' meets 'Nature').
    - NARRATIVE FIRST: Do not start with "Recent studies show". Start with a scene, a sensory detail, or a provocative question.
    - SKEPTICAL WONDER: Celebrate the discovery, but analyze the limitations.
    - NO AI PATTERNS: Strictly forbid the words: "delve", "testament", "tapestry", "landscape", "game-changer", "in conclusion", "unmasking".
    - NO HASHTAGS anywhere.
    
    STRUCTURE:
    1. <h1>{title}</h1> (Use this exact title tag)
    2. The Hook (Narrative intro)
    3. The Science (Deep dive into the mechanism/data)
    4. The Context (Why this matters to Entomology/Neuroscience/Ecology)
    5. The Traveler's Angle (Where can a non-scientist go to see this? A museum? A specific region? A dark sky park?)
    6. Sources (Link to original story)
    """
    
    user_prompt = f"""
    HEADLINE: {title}
    SUMMARY: {desc}
    SOURCE: {source}
    
    Write the article now. Start directly with the <h1> tag.
    """

    # LIST OF MODELS TO TRY (In order of stability/free-tier limits)
    # We prefer Flash (fast/cheap) -> Flash 8b -> Pro 1.0 (Older/Stable)
    model_cascade = [
        "gemini-2.5-flash",
        "gemini-1.5-flash-8b",
        "gemini-1.0-pro",
        "gemini-1.5-pro"
    ]
    
    headers = { "Content-Type": "application/json" }
    payload = {
        "contents": [{"parts": [{"text": system_instruction + "\n\n" + user_prompt}]}],
        "generationConfig": {
            "temperature": 0.7,
            "maxOutputTokens": 2000
        }
    }

    # Iterate through models until one works
    for model in model_cascade:
        print(f"🤖 Attempting generation with model: {model}...")
        api_url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={LLM_API_KEY}"

        try:
            response = requests.post(api_url, headers=headers, json=payload)
            
            # Handle Rate Limit (429) by switching models, NOT waiting
            if response.status_code == 429:
                print(f"   ⚠️ Rate limit hit on {model}. Switching to next model...")
                continue # Skip to next model in list immediately
                
            data = response.json()
            
            # Success Check
            if 'candidates' in data and data['candidates']:
                raw_html = data['candidates'][0]['content']['parts'][0]['text']
                clean_html = raw_html.replace("```html", "").replace("```", "").strip()
                print(f"   ✅ Success with {model}!")
                return title, clean_html
            
            # Other Errors
            if 'error' in data:
                print(f"   ⚠️ Error from {model}: {data['error']['message']}")
                continue # Try next model

        except Exception as e:
            print(f"   ❌ Connection Error ({model}): {e}")
            continue

    print("❌ All AI models failed to generate content.")
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
        # Added User-Agent to headers to prevent 403/Timeout
        headers = { "User-Agent": get_browser_headers()["User-Agent"] }
        r = requests.post(f"{WORDPRESS_URL}/posts", auth=(WP_USER, WP_PASSWORD), json=post_data, headers=headers, timeout=30)
        
        if r.status_code in [200, 201]:
            link = r.json().get('link')
            print(f"✅ SUCCESS! Article Live: {link}")
        else:
            print(f"❌ Publish Failed: {r.status_code} - {r.text}")
            
    except Exception as e:
        print(f"❌ Publish Network Error: {e}")

# --- MAIN LOOP ---
if __name__ == "__main__":
    article = fetch_top_science_story()
    
    if article:
        media_id, uploaded_url = upload_image_to_wordpress(article.get('urlToImage'), article['title'])
        img_ref = uploaded_url if uploaded_url else ""
        
        title, content = write_feature_article(article, img_ref)
        
        if title and content:
            publish_to_wordpress(title, content, media_id)
        else:
            print("⚠️ Skipping publish due to generation failure.")
    else:
        print("🏁 No valid stories found today.")
