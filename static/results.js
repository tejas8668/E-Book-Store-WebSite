let currentPage = 1;
let currentQuery = '';
let isLoading = false;

// Function to create book card HTML
function createBookCard(book) {
    return `
        <div class="book-card">
            <img src="${book.image_url}" alt="${book.title}" loading="lazy">
            <h3>${book.title}</h3>
            <a href="${book.link}" target="_blank">View Book</a>
        </div>
    `;
}

// Function to display books
function displayBooks(books) {
    const booksGrid = document.querySelector('.books-grid');
    booksGrid.innerHTML = books.map(book => createBookCard(book)).join('');
}

// Function to update pagination
function updatePagination(total, currentPage) {
    const prevButton = document.getElementById('prevPage');
    const nextButton = document.getElementById('nextPage');
    const currentPageSpan = document.getElementById('currentPage');

    prevButton.disabled = currentPage === 1;
    nextButton.disabled = total < 10;
    currentPageSpan.textContent = `Page ${currentPage}`;
}

// Function to fetch books from API
async function fetchBooks(query, page = 1) {
    if (isLoading) return;
    
    isLoading = true;
    
    try {
        const response = await fetch(`/api/search?query=${encodeURIComponent(query)}&page=${page}`);
        const data = await response.json();
        
        displayBooks(data.books);
        updatePagination(data.total, page);
        
        currentPage = page;
        currentQuery = query;
    } catch (error) {
        console.error('Error fetching books:', error);
        alert('Error fetching books. Please try again.');
    } finally {
        isLoading = false;
    }
}

// Function to handle pagination
function handlePagination() {
    const prevButton = document.getElementById('prevPage');
    const nextButton = document.getElementById('nextPage');
    
    prevButton.addEventListener('click', () => {
        if (currentPage > 1) {
            fetchBooks(currentQuery, currentPage - 1);
        }
    });
    
    nextButton.addEventListener('click', () => {
        fetchBooks(currentQuery, currentPage + 1);
    });
}

// Initialize the page
document.addEventListener('DOMContentLoaded', () => {
    // Get query parameters from URL
    const urlParams = new URLSearchParams(window.location.search);
    const query = urlParams.get('q');
    const page = parseInt(urlParams.get('page')) || 1;

    if (query) {
        // Update search query display
        document.getElementById('searchQuery').textContent = query;
        // Fetch books
        fetchBooks(query, page);
    } else {
        // Redirect to home if no query
        window.location.href = '/';
    }

    handlePagination();
}); 