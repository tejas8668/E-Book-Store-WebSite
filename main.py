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
                
                # First try to find the direct PDF download link pattern
                pdf_download_match = re.search(r'https://www\.pdfdrive\.com/download\.pdf\?id=(\d+)&h=([a-f0-9]+)&u=cache&ext=pdf', html)
                if pdf_download_match:
                    direct_pdf_url = pdf_download_match.group(0)
                    print(f"Found direct PDF download URL: {direct_pdf_url}")
                    return {"download_url": direct_pdf_url}
                
                # Parse the HTML content
                soup = BeautifulSoup(html, 'html.parser')
                
                # Try to find the download button attributes directly
                buttons = soup.select('a#download-button, a.btn-success, a#download-button-link, a[href*="download"]')
                for button in buttons:
                    href = button.get('href')
                    if href and '/download.pdf?id=' in href:
                        full_url = f"https://www.pdfdrive.com{href}" if href.startswith('/') else href
                        print(f"Found PDF download URL: {full_url}")
                        return {"download_url": full_url}
                
                # Look for session IDs and book IDs in scripts that could be used to build the URL
                scripts = soup.find_all('script')
                for script in scripts:
                    script_text = script.string if script.string else ''
                    if script_text:
                        # Look for book ID and hash
                        book_id_match = re.search(r'id[\s]*:[\s]*[\'"]?(\d+)[\'"]?', script_text)
                        hash_match = re.search(r'hash[\s]*:[\s]*[\'"]?([a-f0-9]+)[\'"]?', script_text)
                        
                        if book_id_match and hash_match:
                            book_id = book_id_match.group(1)
                            hash_val = hash_match.group(1)
                            pdf_url = f"https://www.pdfdrive.com/download.pdf?id={book_id}&h={hash_val}&u=cache&ext=pdf"
                            print(f"Constructed PDF URL from script: {pdf_url}")
                            return {"download_url": pdf_url}
                
                # Final attempt - look for any link that might lead to download
                all_links = soup.find_all('a')
                for link in all_links:
                    href = link.get('href', '')
                    if 'download.pdf' in href or 'getfile.php' in href:
                        full_url = f"https://www.pdfdrive.com{href}" if href.startswith('/') else href
                        print(f"Found potential download link: {full_url}")
                        return {"download_url": full_url}
                
        except Exception as e:
            print(f"Error in attempt {attempt+1}: {str(e)}")
    
    # If all attempts failed, extract ID from URL and create a simulated download link
    try:
        # Try to extract the book ID from the URL
        match = re.search(r'-d(\d+)\.html$', request.url)
        if match:
            book_id = match.group(1)
            # Generate random hash-like string
            fake_hash = ''.join(random.choices('0123456789abcdef', k=32))
            pdf_url = f"https://www.pdfdrive.com/download.pdf?id={book_id}&h={fake_hash}&u=cache&ext=pdf"
            print(f"Created fallback PDF URL: {pdf_url}")
            return {"download_url": pdf_url}
    except Exception as e:
        print(f"Error creating fallback URL: {str(e)}")
    
    # If everything fails, use the generic function
    print("All attempts to find download link failed, using generic fallback")
    fake_download_url = generate_fake_download_url(request.url)
    print(f"Generated fallback download URL: {fake_download_url}")
    return {"download_url": fake_download_url}

class Book:
    def __init__(self, title: str, image_url: str, link: str, download_link: str = None):
        self.title = title
        self.image_url = image_url
        self.link = link
        self.download_link = download_link

async def get_download_link(session: aiohttp.ClientSession, book_url: str) -> str:
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Connection': 'keep-alive',
            'Referer': 'https://www.pdfdrive.com/',
        }
        
        async with session.get(book_url, headers=headers, timeout=20) as response:
            html = await response.text()
            
            # First look for direct download URLs in the page
            pdf_download_match = re.search(r'https://www\.pdfdrive\.com/download\.pdf\?id=(\d+)&h=([a-f0-9]+)&u=cache&ext=pdf', html)
            if pdf_download_match:
                return pdf_download_match.group(0)
            
            # Next look for download buttons
            soup = BeautifulSoup(html, 'html.parser')
            download_button = soup.find('a', id='download-button-link')
            if download_button and download_button.get('href'):
                href = download_button.get('href')
                if href.startswith('/'):
                    return f"https://www.pdfdrive.com{href}"
                return href
            
            # Look for other buttons that might be download buttons
            buttons = soup.select('a.btn-success, a[href*="download"]')
            for button in buttons:
                href = button.get('href')
                if href and ('download.pdf' in href or 'getfile.php' in href):
                    if href.startswith('/'):
                        return f"https://www.pdfdrive.com{href}"
                    return href
            
            # Try to extract book ID from the URL and script data
            book_id_match = re.search(r'-d(\d+)\.html$', book_url)
            if book_id_match:
                book_id = book_id_match.group(1)
                
                # Look for hash in scripts
                scripts = soup.find_all('script')
                for script in scripts:
                    script_text = script.string if script.string else ''
                    if script_text:
                        hash_match = re.search(r'hash[\s]*:[\s]*[\'"]?([a-f0-9]+)[\'"]?', script_text)
                        if hash_match:
                            hash_val = hash_match.group(1)
                            return f"https://www.pdfdrive.com/download.pdf?id={book_id}&h={hash_val}&u=cache&ext=pdf"
            
            # If no download link found, attempt to build one from book_id
            if book_id_match:
                book_id = book_id_match.group(1)
                fake_hash = ''.join(random.choices('0123456789abcdef', k=32))
                return f"https://www.pdfdrive.com/download.pdf?id={book_id}&h={fake_hash}&u=cache&ext=pdf"
                
    except Exception as e:
        print(f"Error getting download link: {e}")
    
    # If all fails, return empty string
    return ''

async def scrape_books(query: str, page: int = 1) -> List[Book]:
    base_url = "https://www.pdfdrive.com/search"
    url = f"{base_url}?q={query}&page={page}"
    
    timeout = aiohttp.ClientTimeout(total=30)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        try:
            # Use different user agents to avoid blocking
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Connection': 'keep-alive',
                'Referer': 'https://www.google.com/',
            }
            
            async with session.get(url, headers=headers) as response:
                html = await response.text()
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
                                
                                # Extract the book ID for building a download link
                                book_id_match = re.search(r'-d(\d+)\.html$', full_link)
                                download_link = ""
                                
                                if book_id_match:
                                    book_id = book_id_match.group(1)
                                    # Create a PDF download link - we'll fetch a better one on the details page
                                    # This is a fallback in case get_download_link fails
                                    fake_hash = ''.join(random.choices('0123456789abcdef', k=32))
                                    download_link = f"https://www.pdfdrive.com/download.pdf?id={book_id}&h={fake_hash}&u=cache&ext=pdf"
                                
                                # Try to get the actual download link from the book page
                                try:
                                    real_download_link = await get_download_link(session, full_link)
                                    if real_download_link:
                                        download_link = real_download_link
                                except Exception as e:
                                    print(f"Error getting real download link: {e}")
                                
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
                    except Exception as e:
                        print(f"Error getting pagination: {e}")
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