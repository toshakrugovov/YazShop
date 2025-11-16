/**
 * Общий JavaScript файл для работы с API
 */

// Получение CSRF токена
function getCookie(name) {
    let cookieValue = null;
    if(document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for(let cookie of cookies){
            cookie = cookie.trim();
            if(cookie.startsWith(name + '=')){
                cookieValue = decodeURIComponent(cookie.slice(name.length + 1));
                break;
            }
        }
    }
    if(!cookieValue){
        const csrfInput = document.querySelector('[name=csrfmiddlewaretoken]');
        if(csrfInput) cookieValue = csrfInput.value;
    }
    return cookieValue;
}

// Базовый fetch для API
async function apiRequest(url, method = 'GET', data = null) {
    const options = {
        method: method,
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCookie('csrftoken')
        },
        credentials: 'same-origin'
    };
    
    if (data && (method === 'POST' || method === 'PUT' || method === 'PATCH')) {
        options.body = JSON.stringify(data);
    }
    
    try {
        const response = await fetch(url, options);
        const result = await response.json();
        
        if (!response.ok) {
            return {
                success: false,
                error: result.error || result.message || 'Ошибка запроса',
                status: response.status
            };
        }
        
        // Если result уже содержит success, возвращаем его как есть
        if (result.success !== undefined) {
            return result;
        }
        
        return {
            success: true,
            data: result
        };
    } catch(err) {
        return {
            success: false,
            error: 'Ошибка соединения: ' + err.message
        };
    }
}

// API для профиля
const ProfileAPI = {
    get: () => apiRequest('/api/profile/', 'GET'),
    update: (data) => apiRequest('/api/profile/', 'PUT', data)
};

// API для адресов
const AddressAPI = {
    getAll: () => apiRequest('/api/addresses/', 'GET'),
    create: (data) => apiRequest('/api/addresses/', 'POST', data),
    get: (id) => apiRequest(`/api/addresses/${id}/`, 'GET'),
    update: (id, data) => apiRequest(`/api/addresses/${id}/`, 'PUT', data),
    delete: (id) => apiRequest(`/api/addresses/${id}/`, 'DELETE')
};

// API для корзины
const CartAPI = {
    get: () => apiRequest('/api/cart/', 'GET'),
    addItem: (data) => apiRequest('/api/cart/', 'POST', data),
    updateItem: (itemId, data) => apiRequest(`/api/cart/items/${itemId}/`, 'PUT', data),
    deleteItem: (itemId) => apiRequest(`/api/cart/items/${itemId}/`, 'DELETE')
};

// API для заказов
const OrderAPI = {
    getAll: () => apiRequest('/api/orders/', 'GET'),
    create: (data) => apiRequest('/api/orders/', 'POST', data),
    get: (id) => apiRequest(`/api/orders/${id}/`, 'GET'),
    cancel: (id) => apiRequest(`/api/orders/${id}/`, 'POST', { action: 'cancel' })
};

// API для карт
const PaymentMethodAPI = {
    getAll: () => apiRequest('/api/payment-methods/', 'GET'),
    create: (data) => apiRequest('/api/payment-methods/', 'POST', data),
    delete: (id) => apiRequest(`/api/payment-methods/${id}/`, 'DELETE'),
    setDefault: (id) => apiRequest(`/api/payment-methods/${id}/`, 'POST', { action: 'set_default' })
};

// API для баланса
const BalanceAPI = {
    get: () => apiRequest('/api/balance/', 'GET'),
    deposit: (data) => apiRequest('/api/balance/', 'POST', data)
};

// API для избранного
const FavoritesAPI = {
    getAll: () => apiRequest('/api/favorites/', 'GET'),
    add: (productId) => apiRequest('/api/favorites/', 'POST', { product_id: productId }),
    remove: (productId) => apiRequest(`/api/favorites/${productId}/`, 'DELETE')
};

// API для поддержки
const SupportAPI = {
    getAll: () => apiRequest('/api/support/', 'GET'),
    create: (data) => apiRequest('/api/support/', 'POST', data),
    get: (id) => apiRequest(`/api/support/${id}/`, 'GET'),
    update: (id, data) => apiRequest(`/api/support/${id}/`, 'PUT', data)
};

// API для каталога
const CatalogAPI = {
    search: (params) => {
        const queryString = new URLSearchParams(params).toString();
        return apiRequest(`/api/catalog/?${queryString}`, 'GET');
    }
};

// API для валидации промокода
const PromoAPI = {
    validate: (data) => apiRequest('/api/validate-promo/', 'POST', data)
};

// API для управления (менеджер/админ)
const ManagementAPI = {
    // Товары
    products: {
        getAll: (params) => {
            const queryString = new URLSearchParams(params).toString();
            return apiRequest(`/api/management/products/?${queryString}`, 'GET');
        },
        create: (data) => apiRequest('/api/management/products/', 'POST', data),
        get: (id) => apiRequest(`/api/management/products/${id}/`, 'GET'),
        update: (id, data) => apiRequest(`/api/management/products/${id}/`, 'PUT', data),
        delete: (id) => apiRequest(`/api/management/products/${id}/`, 'DELETE')
    },
    // Категории
    categories: {
        getAll: () => apiRequest('/api/management/categories/', 'GET'),
        create: (data) => apiRequest('/api/management/categories/', 'POST', data),
        update: (id, data) => apiRequest(`/api/management/categories/${id}/`, 'PUT', data)
    },
    // Бренды
    brands: {
        getAll: () => apiRequest('/api/management/brands/', 'GET'),
        create: (data) => apiRequest('/api/management/brands/', 'POST', data),
        update: (id, data) => apiRequest(`/api/management/brands/${id}/`, 'PUT', data)
    },
    // Заказы
    orders: {
        getAll: (params) => {
            const queryString = new URLSearchParams(params).toString();
            return apiRequest(`/api/management/orders/?${queryString}`, 'GET');
        },
        get: (id) => apiRequest(`/api/management/orders/${id}/`, 'GET'),
        updateStatus: (id, data) => apiRequest(`/api/management/orders/${id}/`, 'POST', data)
    },
    // Пользователи (только админ)
    users: {
        getAll: (params) => {
            const queryString = new URLSearchParams(params).toString();
            return apiRequest(`/api/management/users/?${queryString}`, 'GET');
        },
        create: (data) => apiRequest('/api/management/users/', 'POST', data),
        get: (id) => apiRequest(`/api/management/users/${id}/`, 'GET'),
        update: (id, data) => apiRequest(`/api/management/users/${id}/`, 'PUT', data),
        delete: (id) => apiRequest(`/api/management/users/${id}/`, 'DELETE'),
        toggleBlock: (id) => apiRequest(`/api/management/users/${id}/`, 'POST')
    },
    // Промокоды (только админ)
    promotions: {
        getAll: (params) => {
            const queryString = new URLSearchParams(params).toString();
            return apiRequest(`/api/management/promotions/?${queryString}`, 'GET');
        },
        create: (data) => apiRequest('/api/management/promotions/', 'POST', data),
        get: (id) => apiRequest(`/api/management/promotions/${id}/`, 'GET'),
        update: (id, data) => apiRequest(`/api/management/promotions/${id}/`, 'PUT', data),
        delete: (id) => apiRequest(`/api/management/promotions/${id}/`, 'DELETE')
    },
    // Поставщики (только админ)
    suppliers: {
        getAll: (params) => {
            const queryString = new URLSearchParams(params).toString();
            return apiRequest(`/api/management/suppliers/?${queryString}`, 'GET');
        },
        create: (data) => apiRequest('/api/management/suppliers/', 'POST', data),
        get: (id) => apiRequest(`/api/management/suppliers/${id}/`, 'GET'),
        update: (id, data) => apiRequest(`/api/management/suppliers/${id}/`, 'PUT', data),
        delete: (id) => apiRequest(`/api/management/suppliers/${id}/`, 'DELETE')
    },
    // Роли (только админ)
    roles: {
        getAll: () => apiRequest('/api/management/roles/', 'GET'),
        create: (data) => apiRequest('/api/management/roles/', 'POST', data),
        delete: (id) => apiRequest(`/api/management/roles/${id}/`, 'DELETE')
    },
    // Бэкапы (только админ)
    backups: {
        getAll: (params) => {
            const queryString = new URLSearchParams(params).toString();
            return apiRequest(`/api/management/backups/?${queryString}`, 'GET');
        },
        create: (data) => apiRequest('/api/management/backups/', 'POST', data),
        delete: (id) => apiRequest(`/api/management/backups/${id}/`, 'DELETE')
    }
};

// Экспорт для использования в других скриптах
if (typeof window !== 'undefined') {
    window.API = {
        ProfileAPI,
        AddressAPI,
        CartAPI,
        OrderAPI,
        PaymentMethodAPI,
        BalanceAPI,
        FavoritesAPI,
        SupportAPI,
        CatalogAPI,
        PromoAPI,
        ManagementAPI,
        getCookie,
        apiRequest
    };
}

