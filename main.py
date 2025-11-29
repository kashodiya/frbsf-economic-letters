from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
import requests
from bs4 import BeautifulSoup
import boto3
import json
from typing import List, Dict
from pydantic import BaseModel
import re
from datetime import datetime
from database import init_database, get_database_manager

from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    init_database()
    yield
    # Shutdown (if needed)

app = FastAPI(
    title="FRBSF Economic Letters Analyzer",
    lifespan=lifespan
)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Database manager
db_manager = get_database_manager()

# Bedrock client
bedrock = boto3.client('bedrock-runtime', region_name='us-east-1')

class EconomicLetter(BaseModel):
    title: str
    url: str
    date: str
    summary: str
    content: str

class InsightRequest(BaseModel):
    letter_content: str
    question: str
    letter_url: str = ""  # Optional field for caching

class InsightResponse(BaseModel):
    insight: str

def scrape_economic_letters(limit: int = 10) -> List[Dict]:
    """Scrape economic letters from FRBSF website with database caching"""
    
    # First, try to get from cache
    cached_letters, _ = db_manager.get_letters_from_cache(limit=limit)
    if cached_letters:
        print("📋 Retrieved letters from cache")
        return cached_letters
    
    print("🌐 Cache miss - scraping fresh data from FRBSF website")
    base_url = "https://www.frbsf.org"
    letters_url = "https://www.frbsf.org/research-and-insights/publications/economic-letter/"
    
    try:
        response = requests.get(letters_url, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        
        letters = []
        
        # Find letter links - looking for article elements or similar containers
        article_links = soup.find_all('a', href=re.compile(r'/economic-letter/\d{4}/'))
        
        # Get more letters than requested to build a good cache
        max_letters = max(limit, 20)
        
        for link in article_links[:max_letters]:
            letter_url = base_url + link.get('href') if link.get('href').startswith('/') else link.get('href')
            title = link.get_text(strip=True)
            
            if title and letter_url:
                # Extract date from URL or title if possible
                date_match = re.search(r'/(\d{4})/', letter_url)
                date = date_match.group(1) if date_match else "Unknown"
                
                # Get letter content
                content = scrape_letter_content(letter_url)
                
                letters.append({
                    'title': title,
                    'url': letter_url,
                    'date': date,
                    'summary': content[:500] + "..." if len(content) > 500 else content,
                    'content': content
                })
        
        # Store in database cache
        if letters:
            success = db_manager.store_letters(letters)
            if success:
                print(f"💾 Stored {len(letters)} letters in database cache")
            else:
                print("⚠️  Failed to store letters in database")
        
        return letters[:limit]  # Return only requested amount
    
    except Exception as e:
        print(f"Error scraping letters: {e}")
        # Try to return any cached data even if expired as fallback
        fallback_letters, _ = db_manager.get_letters_from_cache(limit=limit)
        if fallback_letters:
            print("📋 Returning expired cache data as fallback")
            return fallback_letters
        return []

def scrape_letter_content(url: str) -> str:
    """Scrape the full content of an individual economic letter"""
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Try to find the main content area
        content_selectors = [
            '.article-content',
            '.content',
            '.post-content',
            'article',
            '.main-content'
        ]
        
        content = ""
        for selector in content_selectors:
            content_div = soup.select_one(selector)
            if content_div:
                # Remove script and style elements
                for script in content_div(["script", "style"]):
                    script.decompose()
                content = content_div.get_text(strip=True)
                break
        
        # If no specific content area found, get all paragraph text
        if not content:
            paragraphs = soup.find_all('p')
            content = ' '.join([p.get_text(strip=True) for p in paragraphs])
        
        return content
    
    except Exception as e:
        print(f"Error scraping letter content from {url}: {e}")
        return "Content could not be retrieved."

def get_llm_insight(content: str, question: str, letter_url: str = "") -> str:
    """Get insights from AWS Bedrock Claude model with database caching"""
    
    # First, try to get from cache
    if letter_url:
        cached_insight = db_manager.get_cached_insight(letter_url, question)
        if cached_insight:
            print("🧠 Retrieved insight from cache")
            return cached_insight
    
    print("🤖 Cache miss - generating new AI insight")
    
    try:
        prompt = f"""
        Based on the following economic letter content, please answer this question: {question}

        Economic Letter Content:
        {content}

        Please provide a clear, concise, and insightful analysis based on the content provided.
        Format your response using markdown for better readability:
        - Use **bold** for key points and important terms
        - Use bullet points or numbered lists for structured information
        - Use headers (##, ###) to organize different sections of your analysis
        - Use *italics* for emphasis where appropriate
        - Use > blockquotes for important quotes from the letter
        """

        body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 1000,
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        }

        response = bedrock.invoke_model(
            modelId="us.anthropic.claude-sonnet-4-20250514-v1:0",
            body=json.dumps(body),
            contentType="application/json"
        )

        response_body = json.loads(response['body'].read())
        insight_text = response_body['content'][0]['text']
        
        # Store in database cache
        if letter_url and insight_text:
            success = db_manager.store_insight(letter_url, question, insight_text)
            if success:
                print("💾 Stored insight in database cache")
            else:
                print("⚠️  Failed to store insight in database")
        
        return insight_text

    except Exception as e:
        print(f"Error getting LLM insight: {e}")
        return f"Error generating insight: {str(e)}"

@app.get("/", response_class=HTMLResponse)
async def read_root():
    """Serve the main Vue.js application"""
    with open("static/index.html", "r") as f:
        return HTMLResponse(content=f.read())

@app.get("/api/letters")
async def get_letters(page: int = 0, limit: int = 10):
    """Get economic letters with pagination"""
    try:
        offset = page * limit
        letters, has_more = db_manager.get_letters_from_cache(limit=limit, offset=offset)
        
        # If no cached letters, try to scrape new ones
        if not letters and page == 0:
            letters = scrape_economic_letters(limit=limit)
            has_more = len(letters) >= limit
        
        return {
            "letters": letters,
            "has_more": has_more,
            "page": page,
            "limit": limit
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching letters: {str(e)}")

@app.post("/api/insights", response_model=InsightResponse)
async def get_insights(request: InsightRequest):
    """Generate insights for a specific letter and question"""
    try:
        insight = get_llm_insight(request.letter_content, request.question, request.letter_url)
        return InsightResponse(insight=insight)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating insight: {str(e)}")

@app.get("/api/cache/stats")
async def get_cache_stats():
    """Get database and cache statistics"""
    try:
        stats = db_manager.get_cache_stats()
        return stats
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting cache stats: {str(e)}")

@app.post("/api/cache/clear")
async def clear_cache(cache_type: str = None):
    """Clear cache entries"""
    try:
        db_manager.clear_cache(cache_type)
        return {"message": f"Cache cleared successfully" + (f" for type: {cache_type}" if cache_type else "")}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error clearing cache: {str(e)}")

@app.post("/api/letters/refresh")
async def refresh_letters():
    """Force refresh of letters from source (bypass cache)"""
    try:
        # Clear the letters cache first
        db_manager.clear_cache("letters_list")
        # Then fetch fresh data
        letters = scrape_economic_letters(limit=20)  # Get more letters on refresh
        return {"message": f"Refreshed {len(letters)} letters", "count": len(letters)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error refreshing letters: {str(e)}")

@app.get("/api/questions/{letter_url:path}")
async def get_question_history(letter_url: str):
    """Get question history for a specific letter"""
    try:
        from urllib.parse import unquote
        decoded_url = unquote(letter_url)
        history = db_manager.get_question_history(decoded_url)
        return history
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching question history: {str(e)}")

@app.delete("/api/questions/{question_id}")
async def delete_question(question_id: int):
    """Delete a specific question and its answer"""
    try:
        success = db_manager.delete_question(question_id)
        if success:
            return {"message": "Question deleted successfully"}
        else:
            raise HTTPException(status_code=404, detail="Question not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting question: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8888)
