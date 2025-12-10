import os
import requests
import sys
import json

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
    # We look for stories with images (urlToImage) so our layout looks good
    url = f"https://newsapi.org/v2/everything?q=(biology OR astronomy OR geology OR ecology OR neuroscience OR 'climate change')&domains=nature.com,scientificamerican.com,sciencenews.org,nationalgeographic.com,phys.org,smithsonianmag.com&sortBy=publishedAt&language=en&apiKey={NEWS_API_KEY}"
    
    try:
        response = requests.get(url)
        data = response.json()
        
        if data.get('status') == 'ok' and data.get('articles'):
            # Filter for articles that definitely have images
            valid_articles = [a for a in data['articles'] if a.get('urlToImage')]
            print(f"✅ Found {len(valid_articles)} valid articles with images.")
            return valid_articles[:1] # Return the best one
        else:
            print(f"⚠️ NewsAPI Issue: {data}")
            return None
    except Exception as e:
        print(f"❌ NewsAPI Connection Error: {e}")
        return None

# --- 3. THE CRITIC & WRITER (Gemini 1.5 Flash) ---
def generate_article(article):
    print("✍️ Writing the deep-dive feature...")
    
    title = article['title']
    description = article['description']
    source = article['source']['name']
    url = article['url']
    image_url = article['urlToImage']
    
    # ADVANCED PROMPT ENGINEERING
    system_instruction = """
    You are a senior science editor for 'Wandering Science', a magazine blending rigorous research with travel and exploration.
    
    YOUR MANDATE:
    1. WRITE LONG: Produce a 1,000+ word deep-dive feature. Do not write short snippets.
    2. BE ENGAGING: Use a "New Yorker" or "National Geographic" narrative style. Open with a scene, a question, or a vivid description.
    3. NO AI PATTERNS: Strictly forbidden words: "delve", "testament", "tapestry", "in conclusion", "landscape of", "realm".
    4. STRUCTURE: Use HTML formatting.
       - Use <h2> for section headers (at least 3 sections).
       - Use <blockquote> for impactful insights.
       - Use <p> for flowing paragraphs.
    5. CITATIONS: You MUST cite the source material. At the end, include a "Sources & Further Reading" section linking to the original news.
    6. TRAVEL ANGLE: The final section must be "The Traveler's Perspective" - explaining where in the world a traveler could go to witness this science (museums, field sites, observatories).
    """
    
    user_message = f"""
    TOPIC: {title}
    CONTEXT: {description}
    ORIGINAL SOURCE: {source} ({url})
    IMAGE CONTEXT: The article will feature an image of: {image_url}
    
    Write the article now.
    """

    # Using 'gemini-1.5-flash-latest' to fix the "not found" error
    api_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash-latest:generateContent?key={LLM_API_KEY}"
    
    headers = { "Content-Type": "application/json" }
    payload = {
        "contents": [{
            "parts": [{"text": system_instruction + "\n\n" + user_message}]
        }]
    }

    try:
        response = requests.post(api_url, headers=headers, json=payload)
        data = response.json()

        if 'error' in data:
            print(f"⚠️ Gemini Error: {data['error']['message']}")
            return None, None

        if 'candidates' in data and data['candidates']:
            raw_text = data['candidates'][0]['content']['parts'][0]['text']
            # Clean markdown code blocks
            clean_text = raw_text.replace("```html", "").replace("```", "")
            return f"{title}", clean_text
        else:
            print(f"⚠️ Unexpected Gemini Response: {data}")
            return None, None

    except Exception as e:
        print(f"❌ Gemini Connection Error: {e}")
        return None, None

# --- 4. MEDIA UPLOADER (New Feature!) ---
def upload_image_to_wordpress(image_url, title):
    if not image_url: return None
    
    print(f"🖼️ Uploading Featured Image: {image_url}...")
    
    try:
        # 1. Download image to memory
        img_response = requests.get(image_url)
        if img_response.status_code != 200:
            print("   ⚠️ Could not download image.")
            return None
            
        filename = f"science-news-{title[:10].replace(' ', '-').lower()}.jpg"
        
        # 2. Upload to WordPress
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
        "featured_media": featured_media_id # Attach the uploaded image!
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
            # Step 1: Upload Image
            media_id = upload_image_to_wordpress(article.get('urlToImage'), title)
            # Step 2: Post Article with Image attached
            post_to_wordpress(title, article_html, media_id)
        else:
            print("⚠️ Content generation failed.")
    else:
        print("🏁 No news found.")
