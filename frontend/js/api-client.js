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
        const raw = (data && (data.detail || data.message)) || null;
        let message;
        if (!raw) {
            message = data ? JSON.stringify(data) : `HTTP ${response.status}`;
        } else if (typeof raw === 'string') {
            message = raw;
        } else if (Array.isArray(raw) && raw.length > 0) {
            // FastAPI validation errors: [{loc, msg, type}, ...]
            message = raw.map(e => e.msg || JSON.stringify(e)).join('; ');
        } else {
            message = JSON.stringify(raw);
        }
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

/* ── QualificationClient ─────────────────────────────────────────────────────── */

const QUALIFICATION_BASE = '/tmf-api/serviceQualificationManagement/v4/checkServiceQualification';

const QualificationClient = {
    /**
     * List ServiceQualifications with pagination and optional state filter.
     * @param {{ offset?: number, limit?: number, state?: string }} params
     */
    list(params = {}) {
        return apiGet(QUALIFICATION_BASE, params);
    },

    /**
     * Get a single ServiceQualification by ID.
     * @param {string} id
     */
    get(id) {
        return apiGet(`${QUALIFICATION_BASE}/${id}`);
    },

    /**
     * Create a new ServiceQualification request.
     * @param {object} body
     */
    create(body) {
        return apiPost(QUALIFICATION_BASE, body);
    },

    /**
     * Partially update a ServiceQualification (PATCH) — used for state transitions.
     * @param {string} id
     * @param {object} body
     */
    patch(id, body) {
        return apiPatch(`${QUALIFICATION_BASE}/${id}`, body);
    },

    /**
     * Delete a terminal or acknowledged ServiceQualification.
     * @param {string} id
     */
    delete(id) {
        return apiDelete(`${QUALIFICATION_BASE}/${id}`);
    },
};

/* ── CategoryClient (TMFC006 — ServiceCategory) ──────────────────────────────── */

const CATEGORY_BASE = '/tmf-api/serviceCatalogManagement/v4/serviceCategory';

const CategoryClient = {
    /**
     * List ServiceCategories with pagination and optional filters.
     * @param {{ offset?: number, limit?: number, lifecycle_status?: string, is_root?: string }} params
     */
    list(params = {}) { return apiGet(CATEGORY_BASE, params); },

    /**
     * Get a single ServiceCategory by ID.
     * @param {string} id
     */
    get(id) { return apiGet(`${CATEGORY_BASE}/${id}`); },

    /**
     * Create a new ServiceCategory.
     * @param {object} body
     */
    create(body) { return apiPost(CATEGORY_BASE, body); },

    /**
     * Partially update a ServiceCategory (PATCH).
     * @param {string} id
     * @param {object} body
     */
    patch(id, body) { return apiPatch(`${CATEGORY_BASE}/${id}`, body); },

    /**
     * Delete a ServiceCategory.
     * @param {string} id
     */
    delete(id) { return apiDelete(`${CATEGORY_BASE}/${id}`); },
};

/* ── CandidateClient (TMFC006 — ServiceCandidate) ────────────────────────────── */

const CANDIDATE_BASE = '/tmf-api/serviceCatalogManagement/v4/serviceCandidate';

const CandidateClient = {
    /**
     * List ServiceCandidates with pagination and optional lifecycle_status filter.
     * @param {{ offset?: number, limit?: number, lifecycle_status?: string }} params
     */
    list(params = {}) { return apiGet(CANDIDATE_BASE, params); },

    /**
     * Get a single ServiceCandidate by ID.
     * @param {string} id
     */
    get(id) { return apiGet(`${CANDIDATE_BASE}/${id}`); },

    /**
     * Create a new ServiceCandidate.
     * @param {object} body
     */
    create(body) { return apiPost(CANDIDATE_BASE, body); },

    /**
     * Partially update a ServiceCandidate (PATCH).
     * @param {string} id
     * @param {object} body
     */
    patch(id, body) { return apiPatch(`${CANDIDATE_BASE}/${id}`, body); },

    /**
     * Delete a ServiceCandidate.
     * @param {string} id
     */
    delete(id) { return apiDelete(`${CANDIDATE_BASE}/${id}`); },
};

/* ── ServiceCatalogClient (TMFC006 — ServiceCatalog container) ───────────────── */

const SERVICE_CATALOG_BASE = '/tmf-api/serviceCatalogManagement/v4/serviceCatalog';

const ServiceCatalogClient = {
    /**
     * List ServiceCatalogs with pagination and optional lifecycle_status filter.
     * @param {{ offset?: number, limit?: number, lifecycle_status?: string }} params
     */
    list(params = {}) { return apiGet(SERVICE_CATALOG_BASE, params); },

    /**
     * Get a single ServiceCatalog by ID.
     * @param {string} id
     */
    get(id) { return apiGet(`${SERVICE_CATALOG_BASE}/${id}`); },

    /**
     * Create a new ServiceCatalog.
     * @param {object} body
     */
    create(body) { return apiPost(SERVICE_CATALOG_BASE, body); },

    /**
     * Partially update a ServiceCatalog (PATCH).
     * @param {string} id
     * @param {object} body
     */
    patch(id, body) { return apiPatch(`${SERVICE_CATALOG_BASE}/${id}`, body); },

    /**
     * Delete a ServiceCatalog.
     * @param {string} id
     */
    delete(id) { return apiDelete(`${SERVICE_CATALOG_BASE}/${id}`); },
};

/* ── CharacteristicSpecClient (TMF633 — ServiceSpecCharacteristic) ────────────── */

const CharacteristicSpecClient = {
    /**
     * List ServiceSpecCharacteristics for a specification.
     * @param {string} specId
     * @param {{ offset?: number, limit?: number }} params
     */
    listBySpec(specId, params = {}) {
        return apiGet(`${CATALOG_BASE}/${specId}/serviceSpecCharacteristic`, params);
    },

    /**
     * Get a single ServiceSpecCharacteristic.
     * @param {string} specId
     * @param {string} charId
     */
    get(specId, charId) {
        return apiGet(`${CATALOG_BASE}/${specId}/serviceSpecCharacteristic/${charId}`);
    },

    /**
     * Create a new ServiceSpecCharacteristic.
     * @param {string} specId
     * @param {object} body
     */
    create(specId, body) {
        return apiPost(`${CATALOG_BASE}/${specId}/serviceSpecCharacteristic`, body);
    },

    /**
     * Partially update a ServiceSpecCharacteristic (PATCH).
     * @param {string} specId
     * @param {string} charId
     * @param {object} body
     */
    patch(specId, charId, body) {
        return apiPatch(`${CATALOG_BASE}/${specId}/serviceSpecCharacteristic/${charId}`, body);
    },

    /**
     * Delete a ServiceSpecCharacteristic.
     * @param {string} specId
     * @param {string} charId
     */
    delete(specId, charId) {
        return apiDelete(`${CATALOG_BASE}/${specId}/serviceSpecCharacteristic/${charId}`);
    },
};

/* ── CharacteristicValueSpecClient (TMF633 — CharacteristicValueSpecification) ── */

const CharacteristicValueSpecClient = {
    /**
     * List CharacteristicValueSpecifications for a characteristic.
     * @param {string} specId
     * @param {string} charId
     * @param {{ offset?: number, limit?: number }} params
     */
    listByChar(specId, charId, params = {}) {
        return apiGet(
            `${CATALOG_BASE}/${specId}/serviceSpecCharacteristic/${charId}/characteristicValueSpecification`,
            params
        );
    },

    /**
     * Get a single CharacteristicValueSpecification.
     * @param {string} specId
     * @param {string} charId
     * @param {string} vsId
     */
    get(specId, charId, vsId) {
        return apiGet(
            `${CATALOG_BASE}/${specId}/serviceSpecCharacteristic/${charId}/characteristicValueSpecification/${vsId}`
        );
    },

    /**
     * Create a new CharacteristicValueSpecification.
     * @param {string} specId
     * @param {string} charId
     * @param {object} body
     */
    create(specId, charId, body) {
        return apiPost(
            `${CATALOG_BASE}/${specId}/serviceSpecCharacteristic/${charId}/characteristicValueSpecification`,
            body
        );
    },

    /**
     * Delete a CharacteristicValueSpecification.
     * @param {string} specId
     * @param {string} charId
     * @param {string} vsId
     */
    delete(specId, charId, vsId) {
        return apiDelete(
            `${CATALOG_BASE}/${specId}/serviceSpecCharacteristic/${charId}/characteristicValueSpecification/${vsId}`
        );
    },
};

/* ── ServiceCharacteristicClient (TMF638 — ServiceCharacteristic) ────────────── */

const ServiceCharacteristicClient = {
    /**
     * List ServiceCharacteristics for a service instance.
     * @param {string} serviceId
     * @param {{ offset?: number, limit?: number }} params
     */
    listByService(serviceId, params = {}) {
        return apiGet(`${INVENTORY_BASE}/${serviceId}/serviceCharacteristic`, params);
    },

    /**
     * Get a single ServiceCharacteristic.
     * @param {string} serviceId
     * @param {string} charId
     */
    get(serviceId, charId) {
        return apiGet(`${INVENTORY_BASE}/${serviceId}/serviceCharacteristic/${charId}`);
    },

    /**
     * Create a new ServiceCharacteristic.
     * @param {string} serviceId
     * @param {object} body
     */
    create(serviceId, body) {
        return apiPost(`${INVENTORY_BASE}/${serviceId}/serviceCharacteristic`, body);
    },

    /**
     * Partially update a ServiceCharacteristic (PATCH).
     * @param {string} serviceId
     * @param {string} charId
     * @param {object} body
     */
    patch(serviceId, charId, body) {
        return apiPatch(`${INVENTORY_BASE}/${serviceId}/serviceCharacteristic/${charId}`, body);
    },

    /**
     * Delete a ServiceCharacteristic.
     * @param {string} serviceId
     * @param {string} charId
     */
    delete(serviceId, charId) {
        return apiDelete(`${INVENTORY_BASE}/${serviceId}/serviceCharacteristic/${charId}`);
    },
};

/* ── CharacteristicValueClient (TMF638 — CharacteristicValue) ────────────────── */

const CharacteristicValueClient = {
    /**
     * List CharacteristicValues for a service characteristic.
     * @param {string} serviceId
     * @param {string} charId
     * @param {{ offset?: number, limit?: number }} params
     */
    listByChar(serviceId, charId, params = {}) {
        return apiGet(
            `${INVENTORY_BASE}/${serviceId}/serviceCharacteristic/${charId}/characteristicValue`,
            params
        );
    },

    /**
     * Get a single CharacteristicValue.
     * @param {string} serviceId
     * @param {string} charId
     * @param {string} valId
     */
    get(serviceId, charId, valId) {
        return apiGet(
            `${INVENTORY_BASE}/${serviceId}/serviceCharacteristic/${charId}/characteristicValue/${valId}`
        );
    },

    /**
     * Create a new CharacteristicValue.
     * @param {string} serviceId
     * @param {string} charId
     * @param {object} body
     */
    create(serviceId, charId, body) {
        return apiPost(
            `${INVENTORY_BASE}/${serviceId}/serviceCharacteristic/${charId}/characteristicValue`,
            body
        );
    },

    /**
     * Delete a CharacteristicValue.
     * @param {string} serviceId
     * @param {string} charId
     * @param {string} valId
     */
    delete(serviceId, charId, valId) {
        return apiDelete(
            `${INVENTORY_BASE}/${serviceId}/serviceCharacteristic/${charId}/characteristicValue/${valId}`
        );
    },
};
