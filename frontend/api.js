/**
 * EvidenceX Client API Adapter (Phase 8)
 * Connects frontend UI to FastAPI backend, Supabase DB, and AI pipelines.
 * Supports both LIVE execution and explicitly labeled DEMO mode.
 * Zero credentials exposed.
 */

(function (global) {
  'use strict';

  // Config & Endpoint resolution
  const DEFAULT_BACKEND_PORT = 8000;
  
  function resolveApiBaseUrl() {
    if (global.__EVIDENCEX_API_URL__) {
      return global.__EVIDENCEX_API_URL__.replace(/\/+$/, '');
    }
    const stored = localStorage.getItem('ex_api_url');
    if (stored) {
      return stored.replace(/\/+$/, '');
    }
    // If served on backend port or same host
    if (typeof window !== 'undefined' && window.location && window.location.origin) {
      if (window.location.port === String(DEFAULT_BACKEND_PORT)) {
        return window.location.origin;
      }
    }
    return `http://localhost:${DEFAULT_BACKEND_PORT}`;
  }

  const API_BASE = resolveApiBaseUrl();
  const CANONICAL_LIVE_INV_ID = "dae39d5b-9698-4283-9154-f0275d4640b1";

  // Mode management: LIVE (default) vs DEMO
  function getMode() {
    return localStorage.getItem('ex_mode') || 'LIVE';
  }

  function setMode(mode) {
    const m = (mode || 'LIVE').toUpperCase();
    localStorage.setItem('ex_mode', m);
    return m;
  }

  function isDemoMode() {
    return getMode() === 'DEMO';
  }

  // Active investigation ID management
  function getActiveInvestigationId() {
    // 1. URL search params
    if (typeof window !== 'undefined' && window.location && window.location.search) {
      const params = new URLSearchParams(window.location.search);
      const fromUrl = params.get('id') || params.get('investigation_id');
      if (fromUrl) {
        localStorage.setItem('ex_active_investigation_id', fromUrl);
        return fromUrl;
      }
    }
    // 2. Stored ID
    const stored = localStorage.getItem('ex_active_investigation_id');
    if (stored) return stored;

    // 3. Canonical verified live investigation
    return CANONICAL_LIVE_INV_ID;
  }

  function setActiveInvestigationId(id) {
    if (id) {
      localStorage.setItem('ex_active_investigation_id', id);
    }
  }

  // Generic fetch wrapper with timeout and JSON error extraction
  async function request(endpoint, options = {}) {
    const url = `${API_BASE}${endpoint.startsWith('/') ? '' : '/'}${endpoint}`;
    const headers = {
      'Accept': 'application/json',
      ...(options.headers || {})
    };

    if (!(options.body instanceof FormData) && !headers['Content-Type'] && options.method && options.method !== 'GET') {
      headers['Content-Type'] = 'application/json';
    }

    const controller = new AbortController();
    const timeoutMs = options.timeoutMs || 45000;
    const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

    try {
      const response = await fetch(url, {
        ...options,
        headers,
        signal: controller.signal
      });
      clearTimeout(timeoutId);

      const contentType = response.headers.get('content-type') || '';
      let data = null;
      if (contentType.includes('application/json')) {
        data = await response.json();
      } else {
        data = await response.text();
      }

      if (!response.ok) {
        const errorDetail = (data && (data.message || data.detail)) || `HTTP ${response.status} ${response.statusText}`;
        const err = new Error(typeof errorDetail === 'string' ? errorDetail : JSON.stringify(errorDetail));
        err.status = response.status;
        err.data = data;
        throw err;
      }

      return data;
    } catch (err) {
      clearTimeout(timeoutId);
      if (err.name === 'AbortError') {
        throw new Error(`Request to ${endpoint} timed out after ${timeoutMs}ms`);
      }
      throw err;
    }
  }

  // ─────────────────────────────────────────────────────────
  // API Endpoints
  // ─────────────────────────────────────────────────────────

  const EvidenceXAPI = {
    API_BASE,
    CANONICAL_LIVE_INV_ID,
    getMode,
    setMode,
    isDemoMode,
    getActiveInvestigationId,
    setActiveInvestigationId,

    // Health & System Status
    async getHealth() {
      return request('/api/v1/health');
    },

    async getSystemStatus() {
      return request('/api/v1/system/status');
    },

    // Ingestion & Intake (Verification Center)
    async verifyText({ text, context, depth = 'standard', evidencePreference = 'balanced', language = 'en', mode }) {
      const body = {
        text: text.trim(),
        context: context ? context.trim() : null,
        depth: depth.toLowerCase(),
        evidence_preference: evidencePreference.toLowerCase(),
        language: language.toLowerCase(),
        mode: (mode || getMode()).toUpperCase()
      };
      const res = await request('/api/v1/verify/text', {
        method: 'POST',
        body: JSON.stringify(body)
      });
      if (res && res.investigation_id) {
        setActiveInvestigationId(res.investigation_id);
      }
      return res;
    },

    async verifyUrl({ url, context, depth = 'standard', evidencePreference = 'balanced', language = 'en', mode }) {
      const body = {
        url: url.trim(),
        context: context ? context.trim() : null,
        depth: depth.toLowerCase(),
        evidence_preference: evidencePreference.toLowerCase(),
        language: language.toLowerCase(),
        mode: (mode || getMode()).toUpperCase()
      };
      const res = await request('/api/v1/verify/url', {
        method: 'POST',
        body: JSON.stringify(body)
      });
      if (res && res.investigation_id) {
        setActiveInvestigationId(res.investigation_id);
      }
      return res;
    },

    async verifyImage({ file, context, depth = 'standard', evidencePreference = 'balanced', language = 'en', mode }) {
      const formData = new FormData();
      formData.append('file', file);
      if (context) formData.append('context', context.trim());
      formData.append('depth', depth.toLowerCase());
      formData.append('evidence_preference', evidencePreference.toLowerCase());
      formData.append('language', language.toLowerCase());
      formData.append('mode', (mode || getMode()).toUpperCase());

      const res = await request('/api/v1/verify/image', {
        method: 'POST',
        body: formData
      });
      if (res && res.investigation_id) {
        setActiveInvestigationId(res.investigation_id);
      }
      return res;
    },

    async verifyAudio({ file, context, depth = 'standard', evidencePreference = 'balanced', language = 'en', mode }) {
      const formData = new FormData();
      formData.append('file', file);
      if (context) formData.append('context', context.trim());
      formData.append('depth', depth.toLowerCase());
      formData.append('evidence_preference', evidencePreference.toLowerCase());
      formData.append('language', language.toLowerCase());
      formData.append('mode', (mode || getMode()).toUpperCase());

      const res = await request('/api/v1/verify/audio', {
        method: 'POST',
        body: formData
      });
      if (res && res.investigation_id) {
        setActiveInvestigationId(res.investigation_id);
      }
      return res;
    },

    // Investigations
    async getInvestigation(id) {
      const invId = id || getActiveInvestigationId();
      return request(`/api/v1/investigations/${invId}`);
    },

    async getInvestigationStatus(id) {
      const invId = id || getActiveInvestigationId();
      return request(`/api/v1/investigations/${invId}/status`);
    },

    async getInvestigationClaims(id) {
      const invId = id || getActiveInvestigationId();
      return request(`/api/v1/investigations/${invId}/claims`);
    },

    async getInvestigationEvidence(id, params = {}) {
      const invId = id || getActiveInvestigationId();
      const q = new URLSearchParams();
      if (params.claimId) q.append('claim_id', params.claimId);
      if (params.stance && params.stance !== 'all') q.append('stance', params.stance);
      if (params.sourceCategory && params.sourceCategory !== 'all') q.append('source_category', params.sourceCategory);
      if (params.sourceQuality && params.sourceQuality !== 'all') q.append('source_quality', params.sourceQuality);
      if (params.startDate) q.append('start_date', params.startDate);
      if (params.endDate) q.append('end_date', params.endDate);
      if (params.query) q.append('query', params.query);

      const qs = q.toString() ? `?${q.toString()}` : '';
      return request(`/api/v1/investigations/${invId}/evidence${qs}`);
    },

    async getInvestigationSources(id) {
      const invId = id || getActiveInvestigationId();
      return request(`/api/v1/investigations/${invId}/sources`);
    },

    async triggerEvidenceRetrieval(id) {
      const invId = id || getActiveInvestigationId();
      return request(`/api/v1/investigations/${invId}/retrieve-evidence`, {
        method: 'POST'
      });
    },

    async triggerVerification(id) {
      const invId = id || getActiveInvestigationId();
      return request(`/api/v1/investigations/${invId}/verify`, {
        method: 'POST'
      });
    },

    async getInvestigationVerificationResults(id) {
      const invId = id || getActiveInvestigationId();
      return request(`/api/v1/investigations/${invId}/verification-results`);
    },

    async getInvestigationResults(id) {
      const invId = id || getActiveInvestigationId();
      return request(`/api/v1/investigations/${invId}/results`);
    },

    async getInvestigationTimeline(id) {
      const invId = id || getActiveInvestigationId();
      return request(`/api/v1/investigations/${invId}/timeline`);
    },

    async queryCopilot(id, message) {
      const invId = id || getActiveInvestigationId();
      return request(`/api/v1/investigations/${invId}/copilot`, {
        method: 'POST',
        body: JSON.stringify({ message: message.trim() })
      });
    },

    async getCopilotHistory(id) {
      const invId = id || getActiveInvestigationId();
      return request(`/api/v1/investigations/${invId}/copilot`);
    },

    // Atomic Claims
    async getClaim(claimId) {
      return request(`/api/v1/claims/${claimId}`);
    },

    async getClaimEvidence(claimId) {
      return request(`/api/v1/claims/${claimId}/evidence`);
    },

    async getClaimVerification(claimId) {
      return request(`/api/v1/claims/${claimId}/verification`);
    },

    async getClaimInvestigation(claimId) {
      return request(`/api/v1/claims/${claimId}/investigation`);
    },

    // Evidence Items
    async getEvidenceDetail(evidenceId) {
      return request(`/api/v1/evidence/${evidenceId}`);
    },

    // Analytics
    async getAnalyticsOverview() {
      return request('/api/v1/analytics/overview');
    },

    // Settings
    async getSettings() {
      return request('/api/v1/settings');
    },

    async updateSettings(settings) {
      return request('/api/v1/settings', {
        method: 'PUT',
        body: JSON.stringify(settings)
      });
    }
  };

  // Expose to window / global
  global.EvidenceXAPI = EvidenceXAPI;

})(typeof window !== 'undefined' ? window : this);
