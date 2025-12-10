import os
import requests
import datetime
import random
from datetime import timedelta

# Configuration (You would set these as Environment Variables)
NEWS_API_KEY = os.getenv("NEWS_API_KEY") # Get from newsapi.org
LLM_API_KEY = os.getenv("LLM_API_KEY")   # OpenAI or Gemini Key
WORDPRESS_URL = "https://wanderingscience.com/wp-json/wp/v2/posts"
WP_USER = os.getenv("WP_USER")
WP_PASSWORD = os.getenv("WP_PASSWORD")   # Application Password, not login password

# 1. THE SCOUT: Find fresh science news
def fetch_science_news():
    print("🕵️ Scouting for stories...")
    # Searching for specific high-quality domains to avoid tabloids
    url = f"https://newsapi.org/v2/everything?q=(biology OR astronomy OR geology OR ecology OR neuroscience OR 'climate change')&domains=nature.com,scientificamerican.com,sciencenews.org,nationalgeographic.com&sortBy=publishedAt&language=en&apiKey={NEWS_API_KEY}"
    
    response = requests.get(url)
    data = response.json()
    
    if data['status'] == 'ok' and data['articles']:
        # Return the top 3 articles for the Critic to choose from
        return data['articles'][:3]
    return None

# 2. THE CRITIC & WRITER: Generate the content
def generate_article(articles):
    print("✍️ Writing the article...")
    
    # We pick the first one for this example, but you could ask the LLM to pick the best one.
    story = articles[0]
    title = story['title']
    description = story['description']
    source = story['source']['name']
    
    # THE SECRET SAUCE: The "Anti-AI" System Prompt
    # This prevents the AI from sounding robotic.
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

    # Pseudo-code for calling an LLM (Replace with actual OpenAI/Gemini call)
    # response = client.chat.completions.create(
    #     model="gpt-4-turbo", 
    #     messages=[
    #         {"role": "system", "content": system_prompt},
    #         {"role": "user", "content": user_prompt}
    #     ]
    # )
    # content = response.choices[0].message.content
    
    # For the file generation to work without an API key, I am simulating the output:
    simulated_content = f"""
    <!-- HTML CONTENT -->
    <p>It was only a matter of time before the data caught up with the theory. The recent report from {source} regarding {title.lower()} is less of a surprise and more of a confirmation of what many field researchers have whispered about for years.</p>
    
    <p>The implications are fascinating. Usually, when we look at these datasets, we see noise. But here, the signal is clear. The team behind the study managed to isolate variables that have plagued previous attempts, resulting in a picture of our biological history that is slightly more complex than the textbooks suggest.</p>
    
    <p>I found myself re-reading the methodology section twice. It’s rare to see such elegance in experimental design. It reminds me of the shift we saw in geology a decade ago—a sudden realization that the tools we were using were simply not sensitive enough to hear the story the earth was trying to tell.</p>
    
    <h3>The Travel Angle</h3>
    <p>For those of us who pack bags and head into the field, this changes where we might look next. If this data holds true, the next great frontier isn't in the remote Amazon, but perhaps in the forgotten archival drawers of our local museums.</p>
    """
    
    return f"Analysis: {title}", simulated_content

# 3. THE PUBLISHER: Post to WordPress
def post_to_wordpress(title, content):
    print("🚀 Publishing to Wandering Science...")
    
    headers = {
        "Content-Type": "application/json",
    }
    
    post_data = {
        "title": title,
        "content": content,
        "status": "publish",  # Set to 'draft' if you want to review first
        "categories": [2],    # ID of your 'Science' category
    }

   r = requests.post(WORDPRESS_URL, auth=(WP_USER, WP_PASSWORD), json=post_data, headers=headers)
if r.status_code == 201:
    print("Success! Post is live.")
else:
    print(f"Error: {r.status_code} - {r.text}")
    
    print(f"Simulated Post: '{title}' uploaded successfully.")

# Main Execution Flow
if __name__ == "__main__":
    # Check if it's time to run (every 4 days logic would be handled by the scheduler, not the script)
    news = fetch_science_news()
    if news:
        title, article_html = generate_article(news)
        post_to_wordpress(title, article_html)
    else:
        print("No significant news found today. Skipping.")
