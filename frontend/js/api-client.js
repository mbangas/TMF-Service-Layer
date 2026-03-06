/**
 * TMF Service Layer — API Client
 *
 * Reusable fetch wrapper with base URL, error handling, and JSON helpers.
 * Import this module in every HTML page before domain-specific scripts.
 */

const API_BASE_URL = (window.__API_BASE_URL__ || 'http://localhost:8000').replace(/\/$/, '');

/**
 * Core fetch wrapper.
 *
 * @param {string} path         - API path (e.g. '/tmf-api/serviceCatalogManagement/v4/serviceSpecification')
 * @param {RequestInit} options - Standard fetch options (method, body, headers, …)
 * @returns {Promise<{data: any, headers: Headers, status: number}>}
 */
async function apiFetch(path, options = {}) {
    const url = `${API_BASE_URL}${path}`;

    const defaultHeaders = {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
    };

    const config = {
        ...options,
        headers: {
            ...defaultHeaders,
            ...(options.headers || {}),
        },
    };

    const response = await fetch(url, config);

    // 204 No Content — return null body
    if (response.status === 204) {
        return { data: null, headers: response.headers, status: response.status };
    }

    let data = null;
    const contentType = response.headers.get('Content-Type') || '';
    if (contentType.includes('application/json')) {
        data = await response.json();
    } else {
        data = await response.text();
    }

    if (!response.ok) {
        const message =
            (data && (data.detail || data.message || JSON.stringify(data))) ||
            `HTTP ${response.status}`;
        const error = new Error(message);
        error.status = response.status;
        error.data = data;
        throw error;
    }

    return { data, headers: response.headers, status: response.status };
}

/* ── Verb helpers ────────────────────────────────────────────────────────────── */

/**
 * HTTP GET
 * @param {string} path
 * @param {Record<string,string|number>} [params] - Query parameters
 */
async function apiGet(path, params = {}) {
    const query = new URLSearchParams(
        Object.entries(params).filter(([, v]) => v !== null && v !== undefined)
            .map(([k, v]) => [k, String(v)])
    ).toString();
    return apiFetch(query ? `${path}?${query}` : path);
}

/**
 * HTTP POST
 * @param {string} path
 * @param {object} body
 */
async function apiPost(path, body) {
    return apiFetch(path, { method: 'POST', body: JSON.stringify(body) });
}

/**
 * HTTP PUT
 * @param {string} path
 * @param {object} body
 */
async function apiPut(path, body) {
    return apiFetch(path, { method: 'PUT', body: JSON.stringify(body) });
}

/**
 * HTTP PATCH
 * @param {string} path
 * @param {object} body
 */
async function apiPatch(path, body) {
    return apiFetch(path, { method: 'PATCH', body: JSON.stringify(body) });
}

/**
 * HTTP DELETE
 * @param {string} path
 */
async function apiDelete(path) {
    return apiFetch(path, { method: 'DELETE' });
}

/* ── Toast notifications ─────────────────────────────────────────────────────── */

/**
 * Display a brief toast notification.
 *
 * @param {string} message
 * @param {'success'|'error'|'info'} [type='info']
 * @param {number} [duration=3500] - Milliseconds before auto-dismiss
 */
function showToast(message, type = 'info', duration = 3500) {
    let container = document.getElementById('toast-container');
    if (!container) {
        container = document.createElement('div');
        container.id = 'toast-container';
        container.className = 'toast-container';
        document.body.appendChild(container);
    }

    const icons = { success: '✓', error: '✕', info: 'ℹ' };

    const toast = document.createElement('div');
    toast.className = `toast toast--${type}`;
    toast.innerHTML = `<span>${icons[type] || icons.info}</span> <span>${message}</span>`;
    container.appendChild(toast);

    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateY(8px)';
        toast.style.transition = 'opacity 0.2s ease, transform 0.2s ease';
        setTimeout(() => toast.remove(), 200);
    }, duration);
}

/* ── Resource-specific clients ───────────────────────────────────────────────── */

const CATALOG_BASE = '/tmf-api/serviceCatalogManagement/v4/serviceSpecification';

const CatalogClient = {
    /**
     * List ServiceSpecifications with pagination.
     * @param {{ offset?: number, limit?: number, lifecycle_status?: string }} params
     */
    list(params = {}) {
        return apiGet(CATALOG_BASE, params);
    },

    /**
     * Get a single ServiceSpecification by ID.
     * @param {string} id
     */
    get(id) {
        return apiGet(`${CATALOG_BASE}/${id}`);
    },

    /**
     * Create a new ServiceSpecification.
     * @param {object} body
     */
    create(body) {
        return apiPost(CATALOG_BASE, body);
    },

    /**
     * Partially update a ServiceSpecification (PATCH).
     * @param {string} id
     * @param {object} body
     */
    patch(id, body) {
        return apiPatch(`${CATALOG_BASE}/${id}`, body);
    },

    /**
     * Delete a ServiceSpecification.
     * @param {string} id
     */
    delete(id) {
        return apiDelete(`${CATALOG_BASE}/${id}`);
    },
};

/* ── OrderClient ─────────────────────────────────────────────────────────────── */

const ORDER_BASE = '/tmf-api/serviceOrdering/v4/serviceOrder';

const OrderClient = {
    /**
     * List ServiceOrders with pagination and optional state filter.
     * @param {{ offset?: number, limit?: number, state?: string }} params
     */
    list(params = {}) {
        return apiGet(ORDER_BASE, params);
    },

    /**
     * Get a single ServiceOrder by ID.
     * @param {string} id
     */
    get(id) {
        return apiGet(`${ORDER_BASE}/${id}`);
    },

    /**
     * Create a new ServiceOrder.
     * @param {object} body
     */
    create(body) {
        return apiPost(ORDER_BASE, body);
    },

    /**
     * Partially update a ServiceOrder (PATCH) — used for lifecycle transitions.
     * @param {string} id
     * @param {object} body
     */
    patch(id, body) {
        return apiPatch(`${ORDER_BASE}/${id}`, body);
    },

    /**
     * Delete a cancelled ServiceOrder.
     * @param {string} id
     */
    delete(id) {
        return apiDelete(`${ORDER_BASE}/${id}`);
    },
};

/* ── InventoryClient ─────────────────────────────────────────────────────────── */

const INVENTORY_BASE = '/tmf-api/serviceInventory/v4/service';

const InventoryClient = {
    /**
     * List Service instances with pagination and optional state filter.
     * @param {{ offset?: number, limit?: number, state?: string }} params
     */
    list(params = {}) {
        return apiGet(INVENTORY_BASE, params);
    },

    /**
     * Get a single Service instance by ID.
     * @param {string} id
     */
    get(id) {
        return apiGet(`${INVENTORY_BASE}/${id}`);
    },

    /**
     * Create a new Service instance.
     * @param {object} body
     */
    create(body) {
        return apiPost(INVENTORY_BASE, body);
    },

    /**
     * Partially update a Service instance (PATCH) — used for lifecycle transitions.
     * @param {string} id
     * @param {object} body
     */
    patch(id, body) {
        return apiPatch(`${INVENTORY_BASE}/${id}`, body);
    },

    /**
     * Delete a terminated or inactive Service instance.
     * @param {string} id
     */
    delete(id) {
        return apiDelete(`${INVENTORY_BASE}/${id}`);
    },
};

/* ── ProvisioningClient ──────────────────────────────────────────────────────── */

const PROVISIONING_BASE = '/tmf-api/serviceActivationConfiguration/v4/serviceActivationJob';

const ProvisioningClient = {
    /**
     * List ServiceActivationJobs with pagination and optional filters.
     * @param {{ offset?: number, limit?: number, state?: string, job_type?: string, service_id?: string }} params
     */
    list(params = {}) {
        return apiGet(PROVISIONING_BASE, params);
    },

    /**
     * Get a single ServiceActivationJob by ID.
     * @param {string} id
     */
    get(id) {
        return apiGet(`${PROVISIONING_BASE}/${id}`);
    },

    /**
     * Create a new ServiceActivationJob.
     * @param {object} body
     */
    create(body) {
        return apiPost(PROVISIONING_BASE, body);
    },

    /**
     * Partially update a ServiceActivationJob (PATCH) — used for state transitions.
     * @param {string} id
     * @param {object} body
     */
    patch(id, body) {
        return apiPatch(`${PROVISIONING_BASE}/${id}`, body);
    },

    /**
     * Delete a failed or cancelled ServiceActivationJob.
     * @param {string} id
     */
    delete(id) {
        return apiDelete(`${PROVISIONING_BASE}/${id}`);
    },
};
