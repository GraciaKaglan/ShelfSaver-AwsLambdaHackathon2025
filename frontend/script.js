// Initialize Telegram WebApp
const tg = window.Telegram?.WebApp || {
    ready: () => {},
    expand: () => {},
    enableClosingConfirmation: () => {},
    showAlert: (msg) => alert(msg),
    MainButton: {
        setText: () => {},
        show: () => {},
        onClick: () => {}
    },
    initDataUnsafe: null,
    openTelegramLink: (url) => window.open(url, '_blank')
};

// API Configuration - UPDATE WITH YOUR ACTUAL API URL
const API_BASE_URL = 'https://ifv2owwcx7.execute-api.eu-north-1.amazonaws.com/prod';

// Global variables
let currentUserId = 'demo';
let allProducts = [];

// Initialize the app
document.addEventListener('DOMContentLoaded', function() {
    initializeTelegramApp();
    loadUserInfo();
    loadProducts();
    setupEventListeners();
});

function initializeTelegramApp() {
    tg.ready();
    tg.expand();
    tg.enableClosingConfirmation();
    console.log('Telegram WebApp initialized');
}

function loadUserInfo() {
    const user = tg.initDataUnsafe?.user;
    
    if (user) {
        document.getElementById('user-name').textContent = user.first_name || 'User';
        currentUserId = user.id;
    } else {
        document.getElementById('user-name').textContent = 'Demo User';
        currentUserId = 'demo';
    }
}

async function loadProducts() {
    try {
        const productList = document.getElementById('product-list');
        productList.innerHTML = '<div class="loading">📡 Loading products...</div>';
        
        const response = await fetch(`${API_BASE_URL}/products?user_id=${currentUserId}`);
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const data = await response.json();
        allProducts = data.products || [];
        
        console.log('Loaded products:', allProducts);
        
        const transformedProducts = allProducts.map(product => ({
            id: product.product_id,
            name: product.product_name || 'Unknown Product',
            quantity: product.quantity || 'N/A',
            expiry: product.expiry_date || 'Unknown',
            confidence: Math.round(product.confidence || 0),
            barcode: product.barcode,
            status: product.status || 'pending',
            image: product.image_url || generatePlaceholderImage(product.product_name),
            created_at: product.created_at
        }));
        
        displayProducts(transformedProducts);
        
    } catch (error) {
        console.error('Error loading products:', error);
        
        const productList = document.getElementById('product-list');
        productList.innerHTML = `
            <div class="empty-state">
                <h3>🔌 Connection Issue</h3>
                <p>Could not load products from the API.</p>
                <p>Make sure you've scanned some products with the bot first!</p>
                <p><small>Error: ${error.message}</small></p>
            </div>
        `;
        
        // Update stats to 0
        document.getElementById('total-products').textContent = '0';
        document.getElementById('expiring-count').textContent = '0';
        
        tg.showAlert('Could not load products. Make sure to scan some products with the bot first!');
    }
}

function generatePlaceholderImage(productName) {
    const firstLetter = (productName || 'P')[0].toUpperCase();
    return `https://via.placeholder.com/80x80/3390ec/ffffff?text=${firstLetter}`;
}

function displayProducts(products) {
    const productList = document.getElementById('product-list');
    const totalProducts = document.getElementById('total-products');
    const expiringCount = document.getElementById('expiring-count');
    
    // Update stats
    totalProducts.textContent = products.length;
    const expiringSoon = products.filter(p => isExpiringSoon(p.expiry)).length;
    expiringCount.textContent = expiringSoon;
    
    if (products.length === 0) {
        productList.innerHTML = `
            <div class="empty-state">
                <h3>📸 No products scanned yet</h3>
                <p>Send photos to the ShelfSaver bot to get started!</p>
                <p>Use the "Open Bot" button above to scan your first product.</p>
            </div>
        `;
        return;
    }
    
    // Display products
    productList.innerHTML = products.map(product => `
        <div class="product-card" data-product-id="${product.id}">
            <img class="product-image" 
                 src="${product.image}" 
                 alt="Product" 
                 onerror="this.src='${generatePlaceholderImage(product.name)}'">
            <div class="product-info">
                <div class="product-name">${product.name}</div>
                <div class="product-details">
                    ${product.quantity !== 'N/A' ? `<span class="quantity">${product.quantity}</span>` : ''}
                    <span class="expiry-date ${getExpiryClass(product.expiry)}">${product.expiry}</span>
                    ${product.confidence ? `<span class="confidence">${product.confidence}%</span>` : ''}
                </div>
                <div class="product-actions">
                    <button class="edit-btn" onclick="editProduct('${product.id}')">✏️ Edit</button>
                    <button class="validate-btn" onclick="validateProduct('${product.id}')">✅ Validate</button>
                </div>
            </div>
        </div>
    `).join('');
}

function isExpiringSoon(expiry) {
    if (!expiry || expiry === 'Unknown') return false;
    
    try {
        // Handle DD/MM/YY format
        const parts = expiry.split('/');
        if (parts.length === 3) {
            const day = parseInt(parts[0]);
            const month = parseInt(parts[1]) - 1; // JS months are 0-indexed
            let year = parseInt(parts[2]);
            
            // Convert 2-digit year to 4-digit
            if (year < 100) {
                year += year < 50 ? 2000 : 1900;
            }
            
            const expiryDate = new Date(year, month, day);
            const today = new Date();
            const diffTime = expiryDate - today;
            const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));
            
            return diffDays <= 3 && diffDays >= 0;
        }
        return false;
    } catch (error) {
        return false;
    }
}

function getExpiryClass(expiry) {
    if (!expiry || expiry === 'Unknown') return 'unknown';
    
    try {
        const parts = expiry.split('/');
        if (parts.length === 3) {
            const day = parseInt(parts[0]);
            const month = parseInt(parts[1]) - 1;
            let year = parseInt(parts[2]);
            
            if (year < 100) {
                year += year < 50 ? 2000 : 1900;
            }
            
            const expiryDate = new Date(year, month, day);
            const today = new Date();
            const diffTime = expiryDate - today;
            const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));
            
            if (diffDays < 0) return 'expired';
            if (diffDays <= 3) return 'warning';
            return 'safe';
        }
        return 'unknown';
    } catch (error) {
        return 'unknown';
    }
}

async function editProduct(productId) {
    try {
        const product = allProducts.find(p => p.product_id === productId);
        if (!product) {
            tg.showAlert('Product not found!');
            return;
        }
        
        const newName = prompt('Edit product name:', product.product_name);
        const newExpiry = prompt('Edit expiry date (DD/MM/YY):', product.expiry_date);
        const newQuantity = prompt('Edit quantity:', product.quantity);
        
        if (newName !== null || newExpiry !== null || newQuantity !== null) {
            const updateData = { status: 'validated' };
            if (newName !== null && newName !== product.product_name) updateData.product_name = newName;
            if (newExpiry !== null && newExpiry !== product.expiry_date) updateData.expiry_date = newExpiry;
            if (newQuantity !== null && newQuantity !== product.quantity) updateData.quantity = newQuantity;
            
            const updateResponse = await fetch(`${API_BASE_URL}/products/${productId}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(updateData)
            });
            
            if (updateResponse.ok) {
                tg.showAlert('Product updated successfully! ✅');
                loadProducts();
            } else {
                throw new Error('Update failed');
            }
        }
        
    } catch (error) {
        console.error('Edit error:', error);
        tg.showAlert('Could not edit product. Please try again.');
    }
}

async function validateProduct(productId) {
    try {
        const updateResponse = await fetch(`${API_BASE_URL}/products/${productId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ status: 'validated' })
        });
        
        if (updateResponse.ok) {
            tg.showAlert('Product validated! ✅');
            loadProducts();
        } else {
            throw new Error('Validation failed');
        }
        
    } catch (error) {
        console.error('Validation error:', error);
        tg.showAlert('Could not validate product. Please try again.');
    }
}

function openTelegramBot() {
    // Update with your actual bot username
    tg.openTelegramLink('https://web.telegram.org/k/#@shelfsaver_graciaOve_bot');
    // tg.openTelegramLink('https://t.me/shelfsaver_graciaOve_bot');
}

function setupEventListeners() {
    document.getElementById('validate-btn').addEventListener('click', async function() {
        try {
            const pendingProducts = allProducts.filter(p => p.status === 'pending');
            
            if (pendingProducts.length === 0) {
                tg.showAlert('No pending products to validate!');
                return;
            }
            
            for (const product of pendingProducts) {
                await validateProduct(product.product_id);
            }
            
            tg.showAlert(`Validated ${pendingProducts.length} products! ✅`);
            
        } catch (error) {
            tg.showAlert('Could not validate all products. Please try again.');
        }
    });
    
    // Set up Telegram main button
    tg.MainButton.setText('Refresh Products');
    tg.MainButton.show();
    tg.MainButton.onClick(loadProducts);
    
    // Auto-refresh every 30 seconds
    setInterval(loadProducts, 30000);
}