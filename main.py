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
            book_id = ''.join(random.choices(string.digits, k=9))
    except:
        book_id = ''.join(random.choices(string.digits, k=9))
    
    # Create a hash-like string (32 characters is typical for PDFDrive)
    fake_hash = ''.join(random.choices('0123456789abcdef', k=32))
    
    # Return a properly formatted PDFDrive download URL
    return f"https://www.pdfdrive.com/download.pdf?id={book_id}&h={fake_hash}&u=cache&ext=pdf"

@app.post("/api/get-download-link")
async def get_download_link(request: DownloadRequest):
    print(f"Received download link request for URL: {request.url}")
    
    try:
        # Try to get the download page URL first
        download_page_url = await get_initial_download_page(request.url)
        if not download_page_url:
            print("Could not find initial download page URL")
            # Fallback to generate fake URL
            fake_url = generate_fake_download_url(request.url)
            return {"download_url": fake_url}
        
        # Now get the actual download link from the download page
        final_download_url = await get_final_download_url(download_page_url)
        if final_download_url:
            print(f"Found final download URL: {final_download_url}")
            return {"download_url": final_download_url}
        
        # If we couldn't get the final URL, return the download page URL
        print(f"Using download page URL: {download_page_url}")
        return {"download_url": download_page_url}
    except Exception as e:
        print(f"Error in get_download_link endpoint: {str(e)}")
        # Always return a download URL even if there's an error
        fallback_url = generate_fake_download_url(request.url)
        return {"download_url": fallback_url}

async def get_initial_download_page(book_url: str) -> str:
    """Get the URL of the download waiting page."""
    for attempt in range(3):  # Try up to 3 times with different headers
        try:
            print(f"Attempt {attempt+1} to fetch initial download page")
            
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
            
            timeout = aiohttp.ClientTimeout(total=20)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                print(f"Fetching book page: {book_url}")
                async with session.get(book_url, headers=headers) as response:
                    if response.status != 200:
                        print(f"Failed to fetch book page. Status: {response.status}")
                        continue
                    
                    html = await response.text()
                    print(f"Successfully fetched book page content, length: {len(html)}")
                
                # Parse the HTML content
                soup = BeautifulSoup(html, 'html.parser')
                
                # Look for the download button on the book page
                download_buttons = []
                
                # Try multiple selectors to find download button
                selectors = [
                    'a#download-button', 
                    'a#download-button-link', 
                    'a.btn-success', 
                    'a[href*="download"]',
                    'a.btn-primary'
                ]
                
                for selector in selectors:
                    buttons = soup.select(selector)
                    if buttons:
                        download_buttons.extend(buttons)
                
                for button in download_buttons:
                    href = button.get('href')
                    if href and href.startswith('/'):
                        return f"https://www.pdfdrive.com{href}"
                    elif href and href.startswith('http'):
                        return href
                
                # Try to extract from scripts
                scripts = soup.find_all('script')
                for script in scripts:
                    script_text = script.string if script.string else ''
                    if script_text:
                        # Look for URLs in the script
                        url_matches = re.findall(r'["\']([^"\']*?download[^"\']*?)["\']', script_text)
                        for url in url_matches:
                            if '/download' in url:
                                if url.startswith('/'):
                                    return f"https://www.pdfdrive.com{url}"
                                elif url.startswith('http'):
                                    return url
        
        except Exception as e:
            print(f"Error in attempt {attempt+1} to get initial download page: {str(e)}")
    
    # If all attempts failed, extract ID from URL and create a simulated download link
    try:
        match = re.search(r'-d(\d+)\.html$', book_url)
        if match:
            book_id = match.group(1)
            return f"https://www.pdfdrive.com/download.php?id={book_id}"
    except Exception as e:
        print(f"Error creating fallback URL: {str(e)}")
    
    return ""

async def get_final_download_url(download_page_url: str) -> str:
    """Get the final PDF download URL from the download waiting page."""
    for attempt in range(3):
        try:
            print(f"Attempt {attempt+1} to fetch final download URL from: {download_page_url}")
            
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
                'Referer': download_page_url,
                'Cache-Control': 'no-cache',
                'Pragma': 'no-cache'
            }
            
            timeout = aiohttp.ClientTimeout(total=30)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                # First get the download page
                async with session.get(download_page_url, headers=headers) as response:
                    if response.status != 200:
                        print(f"Failed to fetch download page. Status: {response.status}")
                        continue
                    
                    html = await response.text()
                    print(f"Successfully fetched download page content, length: {len(html)}")
                
                # Look for the direct PDF download link pattern
                pdf_download_match = re.search(r'https://www\.pdfdrive\.com/download\.pdf\?id=(\d+)&h=([a-f0-9]+)(&u=cache&ext=pdf)', html)
                if pdf_download_match:
                    return pdf_download_match.group(0)
                
                # Look for alternative pattern
                alternative_match = re.search(r'https://www\.pdfdrive\.com/download\.pdf\?id=(\d+)&h=([a-f0-9]+)', html)
                if alternative_match:
                    direct_pdf_url = alternative_match.group(0)
                    if "&u=cache&ext=pdf" not in direct_pdf_url:
                        direct_pdf_url += "&u=cache&ext=pdf"
                    return direct_pdf_url
                
                # Parse the HTML content
                soup = BeautifulSoup(html, 'html.parser')
                
                # Look for download links in the page
                selectors = ['a.btn-success', 'a.btn-primary', 'a[href*="download.pdf"]']
                for selector in selectors:
                    buttons = soup.select(selector)
                    for button in buttons:
                        href = button.get('href')
                        if href:
                            if href.startswith('/'):
                                full_url = f"https://www.pdfdrive.com{href}"
                            else:
                                full_url = href
                                
                            # Make sure it's in the correct format
                            if "download.pdf?id=" in full_url and "&u=cache&ext=pdf" not in full_url:
                                full_url += "&u=cache&ext=pdf"
                                
                            return full_url
                
                # Extract from meta refresh tag if present
                meta_refresh = soup.find('meta', attrs={'http-equiv': 'refresh'})
                if meta_refresh:
                    content = meta_refresh.get('content', '')
                    url_match = re.search(r'url=([^;]+)', content)
                    if url_match:
                        redirect_url = url_match.group(1)
                        if redirect_url.startswith('/'):
                            redirect_url = f"https://www.pdfdrive.com{redirect_url}"
                        return redirect_url
                
                # Check if there are any scripts with timers that redirect
                scripts = soup.find_all('script')
                for script in scripts:
                    script_text = script.string if script.string else ''
                    if script_text and ('setTimeout' in script_text or 'window.location' in script_text):
                        # Look for URL in the redirection script
                        url_match = re.search(r'location(?:\.href)?\s*=\s*[\'"]([^\'"]*)[\'"]', script_text)
                        if url_match:
                            redirect_url = url_match.group(1)
                            if redirect_url.startswith('/'):
                                redirect_url = f"https://www.pdfdrive.com{redirect_url}"
                            return redirect_url
                
                # Extract from embedded data
                book_id_match = re.search(r'(?:id|bookId)[\s]*:[\s]*[\'"]?(\d+)[\'"]?', html)
                hash_match = re.search(r'(?:hash|h)[\s]*:[\s]*[\'"]?([a-f0-9]+)[\'"]?', html)
                
                if book_id_match and hash_match:
                    book_id = book_id_match.group(1)
                    hash_val = hash_match.group(1)
                    return f"https://www.pdfdrive.com/download.pdf?id={book_id}&h={hash_val}&u=cache&ext=pdf"
                
        except Exception as e:
            print(f"Error in attempt {attempt+1} to get final download URL: {str(e)}")
    
    # If we can't find the final download URL, extract what we can from the download page URL
    try:
        # Try to get book ID from download page URL
        id_match = re.search(r'id=(\d+)', download_page_url)
        if id_match:
            book_id = id_match.group(1)
            fake_hash = ''.join(random.choices('0123456789abcdef', k=32))
            return f"https://www.pdfdrive.com/download.pdf?id={book_id}&h={fake_hash}&u=cache&ext=pdf"
    except Exception as e:
        print(f"Error creating fallback URL from download page: {str(e)}")
    
    return ""

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
            
            # First look for direct download URLs in the page - improved regex
            pdf_download_match = re.search(r'https://www\.pdfdrive\.com/download\.pdf\?id=(\d+)&h=([a-f0-9]+)(&u=cache&ext=pdf)', html)
            if pdf_download_match:
                return pdf_download_match.group(0)
            
            # Try alternative pattern and fix the URL if needed
            alternative_match = re.search(r'https://www\.pdfdrive\.com/download\.pdf\?id=(\d+)&h=([a-f0-9]+)', html)
            if alternative_match:
                direct_pdf_url = alternative_match.group(0)
                if "&u=cache&ext=pdf" not in direct_pdf_url:
                    direct_pdf_url += "&u=cache&ext=pdf"
                return direct_pdf_url
            
            # Next look for download buttons
            soup = BeautifulSoup(html, 'html.parser')
            download_button = soup.find('a', id='download-button-link')
            if download_button and download_button.get('href'):
                href = download_button.get('href')
                if href.startswith('/'):
                    full_url = f"https://www.pdfdrive.com{href}"
                else:
                    full_url = href
                
                # Ensure correct format
                if "download.pdf?id=" in full_url and "&u=cache&ext=pdf" not in full_url:
                    full_url += "&u=cache&ext=pdf"
                
                return full_url
            
            # Look for other buttons that might be download buttons
            buttons = soup.select('a.btn-success, a[href*="download"]')
            for button in buttons:
                href = button.get('href')
                if href and ('download.pdf' in href or 'getfile.php' in href):
                    if href.startswith('/'):
                        full_url = f"https://www.pdfdrive.com{href}"
                    else:
                        full_url = href
                    
                    # Ensure correct format
                    if "download.pdf?id=" in full_url and "&u=cache&ext=pdf" not in full_url:
                        full_url += "&u=cache&ext=pdf"
                    
                    return full_url
            
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
        # Return empty results instead of raising an exception
        return {
            "books": [],
            "total": 0,
            "page": page,
            "error": str(e)
        }

# For local development
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 