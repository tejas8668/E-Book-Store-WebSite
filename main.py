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