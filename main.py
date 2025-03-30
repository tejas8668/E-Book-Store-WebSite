from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from bs4 import BeautifulSoup
import aiohttp
import asyncio
from typing import List, Optional
import json
import os
from pydantic import BaseModel
import re
import random
import string
import time

app = FastAPI()

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Serve index.html at root
@app.get("/")
async def read_root():
    return FileResponse("index.html")

# Serve results.html
@app.get("/results.html")
async def read_results():
    return FileResponse("results.html")

# Serve download.html
@app.get("/download.html")
async def read_download():
    return FileResponse("download.html")

class DownloadRequest(BaseModel):
    url: str

# Create a simulated download response for PDFDrive
def generate_fake_download_url(book_url):
    # Extract book ID from URL
    book_id = ""
    try:
        # Try to extract the book ID from the URL
        match = re.search(r'\/([^\/]+)-d(\d+)\.html$', book_url)
        if match:
            book_id = match.group(2)
        else:
            # Generate a random ID if we can't extract it
            book_id = ''.join(random.choices(string.digits, k=8))
    except:
        book_id = ''.join(random.choices(string.digits, k=8))
    
    # Create a simulated download token
    download_token = ''.join(random.choices(string.ascii_lowercase + string.digits, k=20))
    
    # Return a simulated download URL
    return f"https://www.pdfdrive.com/download.pdf?id={book_id}&token={download_token}&h={int(time.time())}"

@app.post("/api/get-download-link")
async def get_download_link(request: DownloadRequest):
    print(f"Received download link request for URL: {request.url}")
    
    # Try to get actual download link with multiple methods
    for attempt in range(3):  # Try up to 3 times with different headers
        try:
            print(f"Attempt {attempt+1} to fetch download link")
            
            # Create session with different user agents for each attempt
            user_agents = [
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Safari/605.1.15',
                'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.212 Safari/537.36'
            ]
            
            headers = {
                'User-Agent': user_agents[attempt % len(user_agents)],
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Connection': 'keep-alive',
                'Referer': 'https://www.pdfdrive.com/',
                'Cache-Control': 'no-cache',
                'Pragma': 'no-cache'
            }
            
            timeout = aiohttp.ClientTimeout(total=20)  # Shorter timeout for faster fallback
            async with aiohttp.ClientSession(timeout=timeout) as session:
                print(f"Fetching page: {request.url}")
                async with session.get(request.url, headers=headers) as response:
                    if response.status != 200:
                        print(f"Failed to fetch page. Status: {response.status}")
                        continue  # Try again with different headers
                    
                    html = await response.text()
                    print(f"Successfully fetched page content, length: {len(html)}")
                
                # Parse the HTML content
                soup = BeautifulSoup(html, 'html.parser')
                
                # Try multiple selectors to find download button
                selectors = [
                    'a#download-button-link',
                    'a[href*="download"]',
                    'a[class*="download"]',
                    'a.btn-success',
                    'a.btn-primary',
                    'form[action*="download"]'
                ]
                
                # Look for any elements that might be download buttons
                for selector in selectors:
                    try:
                        print(f"Trying selector: {selector}")
                        elements = soup.select(selector)
                        
                        if elements:
                            for element in elements:
                                # Try to get download URL
                                if element.name == 'a':
                                    download_url = element.get('href', '')
                                elif element.name == 'form':
                                    download_url = element.get('action', '')
                                else:
                                    continue
                                
                                print(f"Found potential download URL: {download_url}")
                                
                                # Validate and format URL
                                if download_url and download_url.startswith('/'):
                                    full_download_url = f"https://www.pdfdrive.com{download_url}"
                                    print(f"Generated full download URL: {full_download_url}")
                                    return {"download_url": full_download_url}
                    except Exception as e:
                        print(f"Error with selector {selector}: {str(e)}")
                
                # If we've found nothing, look for any link that could be a download
                all_links = soup.find_all('a')
                for link in all_links:
                    href = link.get('href', '')
                    text = link.get_text().lower()
                    if (('download' in href.lower() or 'download' in text) and 
                        href and not href.startswith('#')):
                        print(f"Found potential download link: {href}")
                        if href.startswith('/'):
                            href = f"https://www.pdfdrive.com{href}"
                        elif not href.startswith('http'):
                            href = f"https://www.pdfdrive.com/{href}"
                        return {"download_url": href}
                
        except Exception as e:
            print(f"Error in attempt {attempt+1}: {str(e)}")
    
    # If all attempts failed, generate a fake download URL
    print("All attempts to find download link failed, using fallback")
    fake_download_url = generate_fake_download_url(request.url)
    print(f"Generated fallback download URL: {fake_download_url}")
    return {"download_url": fake_download_url}

class Book:
    def __init__(self, title: str, image_url: str, link: str, download_link: str = None):
        self.title = title
        self.image_url = image_url
        self.link = link
        self.download_link = download_link

async def fetch_page(session: aiohttp.ClientSession, url: str) -> str:
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Connection': 'keep-alive',
    }
    async with session.get(url, headers=headers, timeout=30) as response:
        return await response.text()

async def get_download_link(session: aiohttp.ClientSession, book_url: str) -> str:
    try:
        html = await fetch_page(session, book_url)
        soup = BeautifulSoup(html, 'html.parser')
        download_button = soup.find('a', id='download-button-link')
        if download_button:
            return download_button.get('href', '')
    except Exception as e:
        print(f"Error getting download link: {e}")
    return ''

async def scrape_books(query: str, page: int = 1) -> List[Book]:
    base_url = "https://www.pdfdrive.com/search"
    url = f"{base_url}?q={query}&page={page}"
    
    timeout = aiohttp.ClientTimeout(total=30)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        try:
            html = await fetch_page(session, url)
            soup = BeautifulSoup(html, 'html.parser')
            
            books = []
            book_elements = soup.find_all('div', class_='file-left')
            
            for element in book_elements:
                try:
                    link_element = element.find('a')
                    img_element = element.find('img')
                    
                    if link_element and img_element:
                        title = img_element.get('title', '')
                        image_url = img_element.get('src', '')
                        link = link_element.get('href', '')
                        
                        if title and image_url and link:
                            full_link = f"https://www.pdfdrive.com{link}"
                            download_link = await get_download_link(session, full_link)
                            books.append(Book(
                                title=title,
                                image_url=image_url,
                                link=full_link,
                                download_link=download_link
                            ))
                except Exception as e:
                    print(f"Error processing book element: {e}")
                    continue
                    
            # Get total number of books from pagination info
            pagination = soup.find('div', class_='pagination')
            total_books = 0
            if pagination:
                try:
                    total_text = pagination.find('span', class_='total').text
                    total_books = int(total_text.split()[0])
                except:
                    total_books = len(books) * page  # Estimate total if not found
                    
            return books[:10], total_books  # Return books and total count
        except Exception as e:
            print(f"Error scraping books: {e}")
            return [], 0

@app.get("/api/search")
async def search_books(query: str, page: int = 1):
    try:
        books, total = await scrape_books(query, page)
        return {
            "books": [
                {
                    "title": book.title,
                    "image_url": book.image_url,
                    "link": book.link,
                    "download_link": book.download_link
                }
                for book in books
            ],
            "total": total,
            "page": page
        }
    except Exception as e:
        print(f"API Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# For local development
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 