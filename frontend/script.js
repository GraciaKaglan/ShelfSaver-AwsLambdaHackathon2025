// Initialize Telegram WebApp
const tg = window.Telegram.WebApp;

// API Configuration - UPDATE THIS WITH YOUR ACTUAL API URL
const API_BASE_URL = 'https://ifv2owwcx7.execute-api.eu-north-1.amazonaws.com/prod'; // You'll need to create this

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
        // Store user ID for API calls
        window.currentUserId = user.id;
    } else {
        document.getElementById('user-name').textContent = 'Demo User';
        window.currentUserId = 'demo';
    }
}

async function loadProducts() {
    try {
        // Show loading state
        const productList = document.getElementById('product-list');
        productList.innerHTML = '<div class="empty-state"><p>📡 Loading products...</p></div>';
        
        // Fetch products from your API
        const response = await fetch(`${API_BASE_URL}/products?user_id=${window.currentUserId}`);
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const data = await response.json();
        const products = data.products || [];
        
        // Transform data to match our UI format
        const transformedProducts = products.map(product => ({
            id: product.product_id,
            name: product.product_name || 'Unknown Product',
            quantity: product.quantity || 'N/A',
            expiry: formatDate(product.expiry_date),
            confidence: product.confidence || 0,
            barcode: product.barcode,
            status: product.status || 'pending',
            image: product.image_url || generatePlaceholderImage(product.product_name),
            created_at: product.created_at
        }));
        
        displayProducts(transformedProducts);
        
    } catch (error) {
        console.error('Error loading products:', error);
        
        // Fallback to demo data if API fails
        const demoProducts = [
            {
                id: 'demo-1',
                name: 'Demo: Connect to your bot first!',
                quantity: '1',
                expiry: '2025-06-25',
                confidence: 95,
                status: 'demo',
                image: generatePlaceholderImage('Demo Product')
            }
        ];
        
        displayProducts(demoProducts);
        
        // Show error to user
        tg.showAlert('Could not load products. Make sure to scan some products with the bot first!');
    }
}

function formatDate(dateString) {
    if (!dateString) return 'Unknown';
    
    // Handle different date formats
    try {
        // Try parsing the date
        const date = new Date(dateString);
        if (isNaN(date.getTime())) {
            // If invalid, return original string
            return dateString;
        }
        
        // Format as DD/MM/YY
        return date.toLocaleDateString('en-GB', {
            day: '2-digit',
            month: '2-digit',
            year: '2-digit'
        });
    } catch (error) {
        return dateString;
    }
}

function generatePlaceholderImage(productName) {
    // Generate a placeholder image URL
    const firstLetter = (productName || 'P')[0].toUpperCase();
    return `https://via.placeholder.com/60x60/3390ec/ffffff?text=${firstLetter}`;
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
                <p>📸 No products scanned yet</p>
                <p>Send photos to the bot to get started!</p>
                <button class="main-btn" onclick="openTelegramBot()" style="margin-top: 15px;">
                    🤖 Open Bot
                </button>
            </div>
        `;
        return;
    }
    
    // Display products
    productList.innerHTML = products.map(product => `
        <div class="product-card" data-product-id="${product.id}">
            <img class="product-image" src="${product.image}" alt="Product" 
                 onerror="this.src='${generatePlaceholderImage(product.name)}'">
            <div class="product-info">
                <div class="product-name">${product.name}</div>
                <div class="product-details">
                    <span class="quantity">${product.quantity}</span>
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
        const today = new Date();
        const expiryDate = new Date(expiry);
        const diffTime = expiryDate - today;
        const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));
        return diffDays <= 3 && diffDays >= 0;
    } catch (error) {
        return false;
    }
}

function getExpiryClass(expiry) {
    if (!expiry || expiry === 'Unknown') return 'unknown';
    
    try {
        const today = new Date();
        const expiryDate = new Date(expiry);
        const diffTime = expiryDate - today;
        const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));
        
        if (diffDays < 0) return 'expired';
        if (diffDays <= 3) return 'warning';
        return 'safe';
    } catch (error) {
        return 'unknown';
    }
}

async function editProduct(productId) {
    // Get current product data
    try {
        const response = await fetch(`${API_BASE_URL}/products/${productId}`);
        const product = await response.json();
        
        // Create edit modal/form (simplified for now)
        const newName = prompt('Edit product name:', product.product_name);
        const newExpiry = prompt('Edit expiry date (DD/MM/YY):', product.expiry_date);
        const newQuantity = prompt('Edit quantity:', product.quantity);
        
        if (newName !== null || newExpiry !== null || newQuantity !== null) {
            const updateData = {};
            if (newName !== null) updateData.product_name = newName;
            if (newExpiry !== null) updateData.expiry_date = newExpiry;
            if (newQuantity !== null) updateData.quantity = newQuantity;
            updateData.status = 'validated';
            
            const updateResponse = await fetch(`${API_BASE_URL}/products/${productId}`, {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(updateData)
            });
            
            if (updateResponse.ok) {
                tg.showAlert('Product updated successfully! ✅');
                loadProducts(); // Reload products
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
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ status: 'validated' })
        });
        
        if (updateResponse.ok) {
            tg.showAlert('Product validated! ✅');
            loadProducts(); // Reload products
        } else {
            throw new Error('Validation failed');
        }
        
    } catch (error) {
        console.error('Validation error:', error);
        tg.showAlert('Could not validate product. Please try again.');
    }
}

function openTelegramBot() {
    // Open the bot in Telegram
    tg.openTelegramLink('https://web.telegram.org/k/#@shelfsaver_graciaOve_bot'); // Update with your bot username
}

function setupEventListeners() {
    // Main button click
    document.getElementById('validate-btn').addEventListener('click', async function() {
        try {
            // Validate all pending products
            const response = await fetch(`${API_BASE_URL}/products?user_id=${window.currentUserId}`);
            const data = await response.json();
            const pendingProducts = data.products.filter(p => p.status === 'pending');
            
            for (const product of pendingProducts) {
                await validateProduct(product.product_id);
            }
            
            tg.showAlert(`Validated ${pendingProducts.length} products! ✅`);
            loadProducts();
            
        } catch (error) {
            tg.showAlert('Could not validate all products. Please try again.');
        }
    });
    
    // Set up Telegram main button
    tg.MainButton.setText('Refresh Products');
    tg.MainButton.show();
    tg.MainButton.onClick(function() {
        loadProducts();
    });
    
    // Refresh every 30 seconds
    setInterval(loadProducts, 30000);
}


// // Initialize Telegram WebApp
// const tg = window.Telegram.WebApp;

// // Initialize the app
// document.addEventListener('DOMContentLoaded', function() {
//     initializeTelegramApp();
//     loadUserInfo();
//     loadProducts();
//     setupEventListeners();
// });

// function initializeTelegramApp() {
//     // Initialize Telegram WebApp
//     tg.ready();
//     tg.expand();
    
//     // Configure the app
//     tg.enableClosingConfirmation();
    
//     console.log('Telegram WebApp initialized');
// }

// function loadUserInfo() {
//     // Get user info from Telegram
//     const user = tg.initDataUnsafe?.user;
    
//     if (user) {
//         document.getElementById('user-name').textContent = user.first_name || 'User';
//     } else {
//         document.getElementById('user-name').textContent = 'Demo User';
//     }
// }

// function loadProducts() {
//     // Mock data for now - later we'll connect to your Lambda API
//     const mockProducts = [
//         {
//             id: '1',
//             name: 'Sample Product',
//             quantity: 5,
//             expiry: '2024-06-25',
//             image: 'https://via.placeholder.com/60x60'
//         }
//     ];
    
//     displayProducts(mockProducts);
// }

// function displayProducts(products) {
//     const productList = document.getElementById('product-list');
//     const totalProducts = document.getElementById('total-products');
//     const expiringCount = document.getElementById('expiring-count');
    
//     // Update stats
//     totalProducts.textContent = products.length;
//     expiringCount.textContent = products.filter(p => isExpiringSoon(p.expiry)).length;
    
//     if (products.length === 0) {
//         productList.innerHTML = `
//             <div class="empty-state">
//                 <p>📸 No products scanned yet</p>
//                 <p>Send photos to the bot to get started!</p>
//             </div>
//         `;
//         return;
//     }
    
//     // Display products
//     productList.innerHTML = products.map(product => `
//         <div class="product-card">
//             <img class="product-image" src="${product.image}" alt="Product" onerror="this.style.display='none'">
//             <div class="product-info">
//                 <div class="product-name">${product.name}</div>
//                 <div class="product-details">
//                     <span class="quantity">${product.quantity}</span>
//                     <span class="expiry-date ${getExpiryClass(product.expiry)}">${product.expiry}</span>
//                 </div>
//             </div>
//         </div>
//     `).join('');
// }

// function isExpiringSoon(expiry) {
//     const today = new Date();
//     const expiryDate = new Date(expiry);
//     const diffTime = expiryDate - today;
//     const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));
//     return diffDays <= 3;
// }

// function getExpiryClass(expiry) {
//     const today = new Date();
//     const expiryDate = new Date(expiry);
//     const diffTime = expiryDate - today;
//     const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));
    
//     if (diffDays < 0) return 'expired';
//     if (diffDays <= 3) return 'warning';
//     return 'safe';
// }

// function setupEventListeners() {
//     // Main button click
//     document.getElementById('validate-btn').addEventListener('click', function() {
//         tg.showAlert('Products validated! ✅');
//     });
    
//     // Set up Telegram main button
//     tg.MainButton.setText('Validate Products');
//     tg.MainButton.show();
//     tg.MainButton.onClick(function() {
//         tg.showAlert('All products validated! ✅');
//     });
// }