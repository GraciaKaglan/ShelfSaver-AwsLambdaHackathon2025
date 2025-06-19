// Initialize Telegram WebApp
const tg = window.Telegram.WebApp;

// Initialize the app
document.addEventListener('DOMContentLoaded', function() {
    initializeTelegramApp();
    loadUserInfo();
    loadProducts();
    setupEventListeners();
});

function initializeTelegramApp() {
    // Initialize Telegram WebApp
    tg.ready();
    tg.expand();
    
    // Configure the app
    tg.enableClosingConfirmation();
    
    console.log('Telegram WebApp initialized');
}

function loadUserInfo() {
    // Get user info from Telegram
    const user = tg.initDataUnsafe?.user;
    
    if (user) {
        document.getElementById('user-name').textContent = user.first_name || 'User';
    } else {
        document.getElementById('user-name').textContent = 'Demo User';
    }
}

function loadProducts() {
    // Mock data for now - later we'll connect to your Lambda API
    const mockProducts = [
        {
            id: '1',
            name: 'Sample Product',
            quantity: 5,
            expiry: '2024-06-25',
            image: 'https://via.placeholder.com/60x60'
        }
    ];
    
    displayProducts(mockProducts);
}

function displayProducts(products) {
    const productList = document.getElementById('product-list');
    const totalProducts = document.getElementById('total-products');
    const expiringCount = document.getElementById('expiring-count');
    
    // Update stats
    totalProducts.textContent = products.length;
    expiringCount.textContent = products.filter(p => isExpiringSoon(p.expiry)).length;
    
    if (products.length === 0) {
        productList.innerHTML = `
            <div class="empty-state">
                <p>📸 No products scanned yet</p>
                <p>Send photos to the bot to get started!</p>
            </div>
        `;
        return;
    }
    
    // Display products
    productList.innerHTML = products.map(product => `
        <div class="product-card">
            <img class="product-image" src="${product.image}" alt="Product" onerror="this.style.display='none'">
            <div class="product-info">
                <div class="product-name">${product.name}</div>
                <div class="product-details">
                    <span class="quantity">${product.quantity}</span>
                    <span class="expiry-date ${getExpiryClass(product.expiry)}">${product.expiry}</span>
                </div>
            </div>
        </div>
    `).join('');
}

function isExpiringSoon(expiry) {
    const today = new Date();
    const expiryDate = new Date(expiry);
    const diffTime = expiryDate - today;
    const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));
    return diffDays <= 3;
}

function getExpiryClass(expiry) {
    const today = new Date();
    const expiryDate = new Date(expiry);
    const diffTime = expiryDate - today;
    const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));
    
    if (diffDays < 0) return 'expired';
    if (diffDays <= 3) return 'warning';
    return 'safe';
}

function setupEventListeners() {
    // Main button click
    document.getElementById('validate-btn').addEventListener('click', function() {
        tg.showAlert('Products validated! ✅');
    });
    
    // Set up Telegram main button
    tg.MainButton.setText('Validate Products');
    tg.MainButton.show();
    tg.MainButton.onClick(function() {
        tg.showAlert('All products validated! ✅');
    });
}