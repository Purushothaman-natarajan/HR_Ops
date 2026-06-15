"""Custom offline API documentation pages — no CDN dependencies.

Professional two-panel layout with sidebar navigation, live search,
schema property tables, auto-generated cURL examples, and copy-to-clipboard.
"""

SWAGGER_UI_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>HR Ops Platform - API Docs (Swagger UI)</title>
<style>
  :root {
    --bg: #0f1117;
    --surface: #1a1d27;
    --surface-2: #22253a;
    --border: #2a2d3a;
    --text: #e4e6ed;
    --text-muted: #8b8fa3;
    --text-dim: #5c5f73;
    --primary: #6366f1;
    --primary-hover: #4f46e5;
    --success: #22c55e;
    --error: #ef4444;
    --warning: #f59e0b;
  }
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', sans-serif;
    background: var(--bg);
    color: var(--text);
    line-height: 1.6;
    font-size: 14px;
  }
  .header {
    position: fixed; top: 0; left: 0; right: 0; height: 56px; z-index: 100;
    background: var(--surface);
    border-bottom: 1px solid var(--border);
    display: flex; align-items: center; gap: 16px;
    padding: 0 24px;
  }
  .header-brand { display: flex; align-items: center; gap: 12px; }
  .header-brand h1 { font-size: 16px; font-weight: 700; }
  .header-brand .version {
    font-size: 10px; font-weight: 600; color: var(--primary);
    background: rgba(99,102,241,0.15); padding: 1px 6px; border-radius: 4px;
  }
  .header-search {
    flex: 1; max-width: 480px; position: relative;
  }
  .header-search input {
    width: 100%; height: 32px; padding: 0 12px 0 32px;
    background: var(--bg); border: 1px solid var(--border); border-radius: 6px;
    color: var(--text); font-size: 13px; outline: none;
  }
  .header-search input:focus { border-color: var(--primary); }
  .header-search .search-icon {
    position: absolute; left: 10px; top: 50%; transform: translateY(-50%);
    color: var(--text-dim); font-size: 14px; pointer-events: none;
  }
  .swagger-ui { margin-top: 56px; }
  .swagger-ui .topbar { display: none !important; }
  .swagger-ui .info { margin: 20px 0; }
  .swagger-ui .info .title { color: var(--text); }
  .swagger-ui .scheme-container { display: none; }
  .swagger-ui .opblock { border-color: var(--border) !important; background: var(--surface) !important; }
  .swagger-ui .opblock-summary { border-color: var(--border) !important; }
  .swagger-ui .opblock-summary-method { border-radius: 4px; }
  .swagger-ui .opblock-tag { border-color: var(--border) !important; }
  .swagger-ui .opblock-tag-section > h3 { border-color: var(--border) !important; color: var(--text); }
  .swagger-ui .btn.execute { background: var(--primary) !important; border-color: var(--primary) !important; }
  .swagger-ui .parameter__name { color: var(--text); }
  .swagger-ui .parameter__type { color: var(--text-muted); }
  .swagger-ui .model-box { background: var(--surface-2) !important; border-color: var(--border) !important; }
  .swagger-ui .model-title { color: var(--text); }
  .swagger-ui .model-prop { border-color: var(--border) !important; }
  .swagger-ui .model-prop:hover { background: rgba(255,255,255,0.02); }
  .swagger-ui .model-description { color: var(--text-muted); }
  .loading { text-align: center; padding: 80px 20px; color: var(--text-muted); }
  .loading .spinner {
    width: 32px; height: 32px; border: 3px solid var(--border);
    border-top-color: var(--primary); border-radius: 50%; animation: spin .6s linear infinite;
    margin: 0 auto 16px;
  }
  @keyframes spin { to { transform: rotate(360deg); } }
  .error { text-align: center; padding: 80px 20px; color: var(--error); }
  .error p { margin-top: 8px; font-size: 13px; color: var(--text-muted); }
</style>
</head>
<body>

<header class="header">
  <div class="header-brand">
    <h1>HR Ops API</h1>
    <span class="version">1.0.0</span>
  </div>
  <div class="header-search">
    <span class="search-icon">&#128269;</span>
    <input id="searchInput" type="text" placeholder="Search endpoints..." oninput="filterEndpoints(this.value)">
  </div>
</header>

<div class="swagger-ui" id="swagger-ui">
  <div class="loading">
    <div class="spinner"></div>
    Loading Swagger UI...
  </div>
</div>

<script src="https://unpkg.com/swagger-ui-dist@5.11.0/swagger-ui-bundle.js" crossorigin></script>
<script src="https://unpkg.com/swagger-ui-dist@5.11.0/swagger-ui-standalone-preset.js" crossorigin></script>
<link rel="stylesheet" href="https://unpkg.com/swagger-ui-dist@5.11.0/swagger-ui.css" crossorigin>

<script>
(function() {
  'use strict';

  window.onload = function() {
    const ui = SwaggerUIBundle({
      url: '/openapi.json',
      dom_id: '#swagger-ui',
      deepLinking: true,
      presets: [
        SwaggerUIBundle.presets.apis,
        SwaggerUIStandalonePreset
      ],
      plugins: [
        SwaggerUIBundle.plugins.DownloadUrl
      ],
      layout: "StandaloneLayout",
      filter: true,
      tryItOutEnabled: true,
      requestInterceptor: (req) => {
        return req;
      },
      onComplete: function(swaggerApi) {
        window.swaggerApi = swaggerApi;
      },
      onFailure: function(err) {
        document.getElementById('swagger-ui').innerHTML =
          '<div class="error"><strong>Failed to load Swagger UI</strong><p>' + err.message + '</p></div>';
      }
    });
  };

  function filterEndpoints(value) {
    if (!window.swaggerApi) return;
    const q = value.trim().toLowerCase();
    window.swaggerApi.filterEndpoints(q ? function(endpoint) {
      const path = endpoint.path || '';
      const method = endpoint.method || '';
      const summary = (endpoint.operation && endpoint.operation.summary) || '';
      const tags = (endpoint.operation && endpoint.operation.tags) || [];
      return path.toLowerCase().includes(q) ||
             method.toLowerCase().includes(q) ||
             summary.toLowerCase().includes(q) ||
             tags.some(t => t.toLowerCase().includes(q));
    } : function() { return true; });
  }
})();
</script>
</body>
</html>
"""

REDOC_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>HR Ops Platform - API Docs</title>
<style>
  :root {
    --bg: #0f1117;
    --surface: #1a1d27;
    --surface-2: #22253a;
    --border: #2a2d3a;
    --text: #e4e6ed;
    --text-muted: #8b8fa3;
    --text-dim: #5c5f73;
    --primary: #6366f1;
    --primary-hover: #4f46e5;
    --success: #22c55e;
    --error: #ef4444;
    --warning: #f59e0b;
    --get: #22c55e;
    --post: #6366f1;
    --put: #f59e0b;
    --delete: #ef4444;
    --radius: 8px;
    --radius-sm: 4px;
    --sidebar-w: 280px;
    --header-h: 64px;
  }
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
  html { scroll-behavior: smooth; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', sans-serif;
    background: var(--bg);
    color: var(--text);
    line-height: 1.6;
    font-size: 14px;
    overflow: hidden;
    height: 100vh;
  }
  ::-webkit-scrollbar { width: 6px; height: 6px; }
  ::-webkit-scrollbar-track { background: transparent; }
  ::-webkit-scrollbar-thumb { background: var(--border); border-radius: 3px; }
  ::-webkit-scrollbar-thumb:hover { background: var(--text-dim); }

  /* ── Header ── */
  .header {
    position: fixed; top: 0; left: 0; right: 0; height: var(--header-h); z-index: 100;
    background: var(--surface);
    border-bottom: 1px solid var(--border);
    display: flex; align-items: center; gap: 16px;
    padding: 0 24px;
  }
  .header-brand { display: flex; align-items: center; gap: 12px; flex-shrink: 0; }
  .header-brand h1 { font-size: 16px; font-weight: 700; white-space: nowrap; }
  .header-brand .version {
    font-size: 10px; font-weight: 600; color: var(--primary);
    background: rgba(99,102,241,0.15); padding: 1px 6px; border-radius: var(--radius-sm);
  }
  .header-search {
    flex: 1; max-width: 480px; position: relative;
  }
  .header-search input {
    width: 100%; height: 36px; padding: 0 14px 0 36px;
    background: var(--bg); border: 1px solid var(--border); border-radius: 8px;
    color: var(--text); font-size: 13px; outline: none; transition: border-color .15s;
  }
  .header-search input:focus { border-color: var(--primary); }
  .header-search input::placeholder { color: var(--text-dim); }
  .header-search .search-icon {
    position: absolute; left: 12px; top: 50%; transform: translateY(-50%);
    color: var(--text-dim); font-size: 14px; pointer-events: none;
  }
  .header-stats { font-size: 12px; color: var(--text-muted); white-space: nowrap; flex-shrink: 0; }
  .header-toggles { display: flex; gap: 6px; flex-shrink: 0; }
  .header-toggles button {
    padding: 6px 12px; font-size: 11px; font-weight: 600; border: 1px solid var(--border);
    border-radius: var(--radius-sm); background: var(--bg); color: var(--text-muted); cursor: pointer;
    transition: all .15s;
  }
  .header-toggles button:hover { border-color: var(--primary); color: var(--text); }
  .hamburger { display: none; width: 36px; height: 36px; align-items: center; justify-content: center; cursor: pointer; border: 1px solid var(--border); border-radius: var(--radius-sm); background: var(--bg); color: var(--text); flex-shrink: 0; }

  /* ── Layout ── */
  .layout { display: flex; height: calc(100vh - var(--header-h)); margin-top: var(--header-h); }

  /* ── Sidebar ── */
  .sidebar {
    width: var(--sidebar-w); flex-shrink: 0; overflow-y: auto;
    background: var(--surface); border-right: 1px solid var(--border); padding: 16px 0;
    transition: transform .2s ease;
  }
  .sidebar-title { font-size: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: 1px; color: var(--text-dim); padding: 0 16px 12px; }
  .sidebar-tag {
    display: flex; align-items: center; gap: 8px; padding: 8px 16px; cursor: pointer;
    font-size: 13px; color: var(--text-muted); transition: all .1s; text-decoration: none;
    border-left: 2px solid transparent;
  }
  .sidebar-tag:hover { background: rgba(255,255,255,0.03); color: var(--text); }
  .sidebar-tag.active { color: var(--text); background: rgba(99,102,241,0.08); border-left-color: var(--primary); }
  .sidebar-tag .count {
    margin-left: auto; font-size: 10px; font-weight: 600; color: var(--text-dim);
    background: var(--bg); padding: 0 6px; border-radius: 10px; min-width: 20px; text-align: center;
  }
  .sidebar-empty { padding: 24px 16px; text-align: center; color: var(--text-dim); font-size: 13px; }

  /* ── Main Content ── */
  .main {
    flex: 1; overflow-y: auto; padding: 24px 32px;
  }
  .content-section { scroll-margin-top: 80px; }
  .section-header {
    display: flex; align-items: center; gap: 12px; margin-bottom: 16px; padding-bottom: 10px;
    border-bottom: 2px solid var(--primary);
  }
  .section-header h2 { font-size: 18px; font-weight: 700; }
  .section-header .count {
    font-size: 11px; font-weight: 600; color: var(--text-muted);
    background: var(--surface-2); padding: 1px 8px; border-radius: 10px;
  }

  /* ── Endpoint Card ── */
  .ep-card {
    background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius);
    margin-bottom: 10px; overflow: hidden; transition: border-color .15s;
  }
  .ep-card:hover { border-color: var(--text-dim); }
  .ep-card-header {
    display: flex; align-items: center; gap: 12px; padding: 12px 16px; cursor: pointer;
    user-select: none; transition: background .1s;
  }
  .ep-card-header:hover { background: rgba(255,255,255,0.02); }
  .ep-chevron {
    font-size: 10px; color: var(--text-dim); transition: transform .2s; flex-shrink: 0;
    width: 16px; text-align: center;
  }
  .ep-chevron.open { transform: rotate(90deg); }
  .ep-method {
    font-size: 11px; font-weight: 700; text-transform: uppercase;
    padding: 3px 10px; border-radius: var(--radius-sm); min-width: 56px; text-align: center;
    flex-shrink: 0; letter-spacing: 0.5px;
  }
  .ep-method.m-get { background: rgba(34,197,94,0.12); color: var(--get); }
  .ep-method.m-post { background: rgba(99,102,241,0.12); color: var(--post); }
  .ep-method.m-put { background: rgba(245,158,11,0.12); color: var(--put); }
  .ep-method.m-delete { background: rgba(239,68,68,0.12); color: var(--delete); }
  .ep-path {
    font-family: 'SF Mono', 'Fira Code', 'Cascadia Code', 'JetBrains Mono', Consolas, monospace;
    font-size: 13px; color: var(--text); flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
  }
  .ep-deprecated { font-size: 10px; font-weight: 600; color: var(--error); background: rgba(239,68,68,0.12); padding: 1px 6px; border-radius: var(--radius-sm); flex-shrink: 0; }
  .ep-summary { font-size: 12px; color: var(--text-muted); flex-shrink: 0; max-width: 35%; text-align: right; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .ep-copy {
    flex-shrink: 0; width: 28px; height: 28px; display: flex; align-items: center; justify-content: center;
    border: none; border-radius: var(--radius-sm); background: transparent; color: var(--text-dim);
    cursor: pointer; font-size: 13px; transition: all .15s; opacity: 0;
  }
  .ep-card-header:hover .ep-copy { opacity: 1; }
  .ep-copy:hover { background: var(--surface-2); color: var(--text); }

  /* ── Endpoint Body ── */
  .ep-body {
    max-height: 0; overflow: hidden; transition: max-height .25s ease;
    border-top: 1px solid var(--border);
  }
  .ep-body.open { max-height: 3000px; }
  .ep-body-inner { padding: 16px; }
  .ep-body h3 {
    font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px;
    color: var(--text-muted); margin-bottom: 8px; margin-top: 20px;
  }
  .ep-body h3:first-child { margin-top: 0; }

  /* ── Description ── */
  .ep-desc {
    font-size: 13px; color: var(--text-muted); margin-bottom: 16px; line-height: 1.7;
    padding: 12px; background: var(--bg); border-radius: var(--radius-sm);
  }

  /* ── Tables ── */
  .tbl-wrap { overflow-x: auto; }
  .tbl-params { width: 100%; border-collapse: collapse; font-size: 12px; }
  .tbl-params thead th {
    text-align: left; padding: 8px 10px; font-weight: 600; color: var(--text-dim);
    border-bottom: 1px solid var(--border); font-size: 11px; text-transform: uppercase; letter-spacing: 0.5px;
  }
  .tbl-params tbody td { padding: 7px 10px; border-bottom: 1px solid var(--border); color: var(--text); vertical-align: top; }
  .tbl-params tbody tr:last-child td { border-bottom: none; }
  .tbl-params tbody tr:hover { background: rgba(255,255,255,0.02); }
  .tbl-params code {
    font-family: 'SF Mono', 'Fira Code', Consolas, monospace;
    font-size: 12px; background: var(--surface-2); padding: 1px 5px; border-radius: 3px;
  }
  .tbl-params .required { color: var(--error); margin-left: 2px; }
  .tbl-params .optional { color: var(--text-dim); font-style: italic; font-size: 11px; }
  .tbl-params .type-badge {
    display: inline-block; font-size: 10px; font-weight: 600;
    padding: 1px 6px; border-radius: 3px; background: var(--surface-2); color: var(--text-muted);
  }
  .tbl-params .type-badge.t-string { background: rgba(99,102,241,0.12); color: var(--post); }
  .tbl-params .type-badge.t-integer { background: rgba(34,197,94,0.12); color: var(--get); }
  .tbl-params .type-badge.t-boolean { background: rgba(245,158,11,0.12); color: var(--put); }
  .tbl-params .type-badge.t-object { background: rgba(239,68,68,0.12); color: var(--error); }
  .tbl-params .type-badge.t-array { background: rgba(99,102,241,0.12); color: var(--post); }
  .tbl-params .type-badge.t-number { background: rgba(34,197,94,0.12); color: var(--get); }

  /* ── Schema ── */
  .schema-prop { margin-bottom: 20px; }
  .schema-prop:last-child { margin-bottom: 0; }

  /* ── cURL ── */
  .curl-box {
    background: #0d0f14; border: 1px solid var(--border); border-radius: var(--radius-sm);
    padding: 12px 14px; position: relative; margin-bottom: 12px;
  }
  .curl-box code {
    font-family: 'SF Mono', 'Fira Code', Consolas, monospace;
    font-size: 12px; color: var(--text); white-space: pre-wrap; word-break: break-all; display: block;
  }
  .curl-box .curl-copy {
    position: absolute; top: 8px; right: 8px; padding: 4px 10px; font-size: 10px; font-weight: 600;
    border: 1px solid var(--border); border-radius: var(--radius-sm); background: var(--surface);
    color: var(--text-muted); cursor: pointer; transition: all .15s;
  }
  .curl-box .curl-copy:hover { border-color: var(--primary); color: var(--text); }

  /* ── Response Schema Table ── */
  .resp-code { font-weight: 700; font-size: 13px; margin-bottom: 4px; }
  .resp-code span { color: var(--text-muted); font-weight: 400; }

  /* ── No results ── */
  .no-results { text-align: center; padding: 60px 20px; color: var(--text-dim); }
  .no-results .icon { font-size: 32px; margin-bottom: 12px; }
  .no-results p { font-size: 14px; }

  /* ── Loading / Error ── */
  .loading, .error {
    text-align: center; padding: 80px 20px;
  }
  .loading { color: var(--text-muted); }
  .loading .spinner {
    width: 32px; height: 32px; border: 3px solid var(--border);
    border-top-color: var(--primary); border-radius: 50%; animation: spin .6s linear infinite;
    margin: 0 auto 16px;
  }
  @keyframes spin { to { transform: rotate(360deg); } }
  .error { color: var(--error); }
  .error p { margin-top: 8px; font-size: 13px; color: var(--text-muted); }

  /* ── Responsive ── */
  @media (max-width: 768px) {
    .hamburger { display: flex; }
    .sidebar {
      position: fixed; top: var(--header-h); left: 0; bottom: 0; z-index: 90;
      transform: translateX(-100%);
    }
    .sidebar.open { transform: translateX(0); }
    .main { padding: 16px; }
    .header-brand h1 { font-size: 14px; }
    .header-stats { display: none; }
    .header-search { max-width: 200px; }
    .header-toggles button { padding: 4px 8px; font-size: 10px; }
    .ep-summary { display: none; }
  }

  /* ── Print friendly ── */
  @media print {
    .sidebar, .header { display: none; }
    .layout { margin-top: 0; }
    .ep-body { max-height: none !important; overflow: visible !important; }
  }
</style>
</head>
<body>

<!-- Header -->
<header class="header">
  <div class="hamburger" onclick="toggleSidebar()" aria-label="Toggle sidebar">&#9776;</div>
  <div class="header-brand">
    <h1>HR Ops API</h1>
    <span class="version">1.0.0</span>
  </div>
  <div class="header-search">
    <span class="search-icon">&#128269;</span>
    <input id="searchInput" type="text" placeholder="Search endpoints, paths, or tags..." oninput="onSearch(this.value)">
  </div>
  <div class="header-toggles">
    <button onclick="expandAll()">Expand all</button>
    <button onclick="collapseAll()">Collapse all</button>
  </div>
  <div class="header-stats" id="stats">Loading...</div>
</header>

<div class="layout">
  <!-- Sidebar -->
  <nav class="sidebar" id="sidebar">
    <div class="sidebar-title">Tags</div>
    <div id="sidebarList"></div>
  </nav>

  <!-- Main -->
  <main class="main" id="content">
    <div class="loading">
      <div class="spinner"></div>
      Loading API specification...
    </div>
  </main>
</div>

<script>
(function(){
  'use strict';

  let spec = null;
  let allEndpoints = [];   // flat array of { tag, el, section }
  let sidebarTags = [];    // sorted tag entries

  // ── Helpers ──
  const esc = s => { if (!s) return ''; return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;'); };

  const typeBadge = type => {
    const t = (type || 'string').toLowerCase();
    const cls = 'type-badge t-' + t;
    return '<span class="' + cls + '">' + esc(t) + '</span>';
  };

  // ── Resolve $ref against components ──
  function resolveRef(obj, components) {
    if (!obj || typeof obj !== 'object') return obj;
    if (obj.$ref && components) {
      const path = obj.$ref.replace('#/components/schemas/', '').split('/');
      let cur = components;
      for (const seg of path) {
        if (!cur) return obj;
        cur = cur[seg];
      }
      if (cur) return resolveRef(cur, components);
    }
    return obj;
  }

  // ── Build schema property table (recursive) ──
  function renderSchema(schema, components, depth) {
    if (!schema) return '';
    schema = resolveRef(schema, components);
    if (!schema) return '<span style="color:var(--text-dim);font-size:12px">any</span>';

    const type = schema.type;
    const props = schema.properties;
    const items = schema.items;
    const enums = schema.enum;
    const oneOf = schema.oneOf;

    if (type === 'array' && items) {
      return '<div style="margin-bottom:6px">' + typeBadge('array') + ' of</div>' + renderSchema(items, components, depth + 1);
    }
    if (oneOf) {
      return oneOf.map((s, i) => {
        const r = resolveRef(s, components);
        return '<div style="margin-bottom:4px"><span class="type-badge" style="background:var(--surface-2);color:var(--text-dim)">' + (r.title || 'Option ' + (i+1)) + '</span></div>' + renderSchema(r, components, depth + 1);
      }).join('');
    }
    if (enums) {
      return '<span class="type-badge">enum</span> ' + enums.map(v => '<code>' + esc(String(v)) + '</code>').join(', ');
    }
    if (type === 'object' || props) {
      if (!props || !Object.keys(props).length) {
        return typeBadge('object');
      }
      let html = '<div class="tbl-wrap"><table class="tbl-params"><thead><tr><th>Property</th><th>Type</th><th>Required</th><th>Description</th></tr></thead><tbody>';
      const required = schema.required || [];
      for (const [name, prop] of Object.entries(props)) {
        const p = resolveRef(prop, components);
        const isReq = required.includes(name);
        const desc = esc(p.description || '');
        let ptype = p.type || 'string';
        let ptypeStr = typeBadge(ptype);
        if (ptype === 'array' && p.items) {
          const inner = resolveRef(p.items, components);
          ptypeStr = typeBadge('array') + ' ' + typeBadge(inner.type || 'object');
        }
        if (ptype === 'object' && p.properties) {
          ptypeStr = '<span class="type-badge t-object">object</span>';
        }
        html += '<tr><td><code>' + esc(name) + '</code></td><td>' + ptypeStr + '</td><td>' + (isReq ? '<span class="required">required</span>' : '<span class="optional">optional</span>') + '</td><td>' + desc + '</td></tr>';
      }
      html += '</tbody></table></div>';
      return html;
    }
    return typeBadge(type || 'string');
  }

  // ── Generate cURL command ──
  function buildCurl(method, path, bodySchema, components) {
    const m = method.toUpperCase();
    const hasBody = ['POST','PUT','PATCH'].includes(m);
    let curl = 'curl -X ' + m + ' \\\n  "http://localhost:8000' + path + '"';
    if (hasBody && bodySchema) {
      const sample = generateSample(bodySchema, components);
      curl += ' \\\n  -H "Content-Type: application/json" \\\n  -d \'' + JSON.stringify(sample, null, 2) + '\'';
    } else if (hasBody) {
      curl += ' \\\n  -H "Content-Type: application/json" \\\n  -d \'{\n    "key": "value"\n  }\'';
    }
    curl += ' \\\n  -H "Authorization: Bearer <token>"';
    return curl;
  }

  function generateSample(schema, components) {
    if (!schema) return {};
    schema = resolveRef(schema, components);
    if (!schema) return {};
    const type = schema.type;
    const props = schema.properties;
    if (type === 'object' && props) {
      const obj = {};
      for (const [name, prop] of Object.entries(props)) {
        const p = resolveRef(prop, components);
        if (!p) continue;
        switch (p.type || 'string') {
          case 'string': obj[name] = p.example || (name === 'password' ? '••••••••' : (name === 'query' ? 'What is the leave policy?' : (name === 'title' ? 'New Title' : 'string'))); break;
          case 'integer': obj[name] = p.example || 0; break;
          case 'number': obj[name] = p.example || 0.0; break;
          case 'boolean': obj[name] = p.example || false; break;
          case 'array': obj[name] = p.example || (p.items ? [generateSample(p.items, components)] : []); break;
          default: obj[name] = null;
        }
      }
      return obj;
    }
    return { key: 'value' };
  }

  // ── Build endpoint detail HTML ──
  function buildDetail(ep, components) {
    const parts = [];
    const desc = ep.description || '';
    const cleanDesc = desc.replace(/^---[\s\S]*?---\s*/m, '').trim();

    if (cleanDesc) {
      // Convert inline code and line breaks
      const formatted = esc(cleanDesc).replace(/\n/g, '<br>');
      parts.push('<div class="ep-desc">' + formatted + '</div>');
    }

    // Parameters
    if (ep.parameters && ep.parameters.length) {
      parts.push('<h3>Parameters</h3>');
      parts.push('<div class="tbl-wrap"><table class="tbl-params"><thead><tr><th>Name</th><th>In</th><th>Type</th><th>Required</th><th>Description</th></tr></thead><tbody>');
      for (const p of ep.parameters) {
        const ps = resolveRef(p.schema, components) || {};
        parts.push('<tr>');
        parts.push('<td><code>' + esc(p.name) + '</code></td>');
        parts.push('<td>' + esc(p.in) + '</td>');
        parts.push('<td>' + typeBadge(ps.type || 'string') + '</td>');
        parts.push('<td>' + (p.required ? '<span class="required">required</span>' : '<span class="optional">optional</span>') + '</td>');
        parts.push('<td>' + esc(p.description || '') + '</td>');
        parts.push('</tr>');
      }
      parts.push('</tbody></table></div>');
    }

    // Request Body
    if (ep.requestBody) {
      const rb = ep.requestBody;
      const content = rb.content;
      if (content) {
        for (const [ct, media] of Object.entries(content)) {
          if (media.schema) {
            parts.push('<h3>Request Body</h3>');
            if (ct !== 'application/json') {
              parts.push('<div style="font-size:11px;color:var(--text-dim);margin-bottom:4px">' + esc(ct) + '</div>');
            }
            parts.push(renderSchema(media.schema, components, 0));
            // cURL example
            parts.push('<h3>Example Request</h3>');
            const curl = buildCurl(ep.method, ep.path, media.schema, components);
            parts.push('<div class="curl-box"><button class="curl-copy" onclick="copyText(this,\'' + esc(curl.replace(/'/g,"\\'")) + '\')">Copy</button><code>' + esc(curl) + '</code></div>');
          }
        }
      }
    } else if (['POST','PUT','PATCH'].includes(ep.method.toUpperCase()) && !ep.requestBody) {
      const curl = buildCurl(ep.method, ep.path, null, null);
      parts.push('<h3>Example Request</h3>');
      parts.push('<div class="curl-box"><button class="curl-copy" onclick="copyText(this,\'' + esc(curl.replace(/'/g,"\\'")) + '\')">Copy</button><code>' + esc(curl) + '</code></div>');
    }

    // Responses
    const responses = ep.responses || {};
    if (Object.keys(responses).length) {
      parts.push('<h3>Responses</h3>');
      for (const [code, resp] of Object.entries(responses)) {
        const isError = parseInt(code) >= 400;
        parts.push('<div class="resp-code"><span style="color:' + (isError ? 'var(--error)' : 'var(--success)') + '">' + esc(code) + '</span> <span>' + esc(resp.description || '') + '</span></div>');
        if (resp.content) {
          for (const [ct, media] of Object.entries(resp.content)) {
            if (media.schema) {
              parts.push(renderSchema(media.schema, components, 0));
            }
          }
        }
      }
    }

    if (!parts.length) {
      return '<div style="color:var(--text-dim);font-size:12px;padding:8px 0">No additional details</div>';
    }
    return parts.join('');
  }

  // ── Render everything ──
  function render(specData) {
    spec = specData;
    const paths = spec.paths || {};
    const components = spec.components || {};
    const schemas = components.schemas || {};
    const comps = { schemas };

    // Build tag -> endpoints map
    const tagMap = {};
    for (const [path, methods] of Object.entries(paths)) {
      for (const [method, detail] of Object.entries(methods)) {
        const tag = (detail.tags && detail.tags[0]) || 'default';
        if (!tagMap[tag]) tagMap[tag] = [];
        tagMap[tag].push({ path, method: method.toUpperCase(), ...detail });
      }
    }

    // Sort tags
    const tagOrder = Object.keys(tagMap).sort();
    sidebarTags = [];

    // Render sidebar
    const sidebarEl = document.getElementById('sidebarList');
    sidebarEl.innerHTML = tagOrder.map(tag => {
      const count = tagMap[tag].length;
      sidebarTags.push({ tag, count });
      return '<a class="sidebar-tag" href="#tag-' + esc(tag) + '" onclick="closeSidebar()">' +
        esc(tag) + '<span class="count">' + count + '</span></a>';
    }).join('');

    // Stats
    const totalEndpoints = tagOrder.reduce((a, t) => a + tagMap[t].length, 0);
    document.getElementById('stats').textContent = totalEndpoints + ' endpoints \u00b7 ' + tagOrder.length + ' tags';

    // Render content
    const content = document.getElementById('content');
    content.innerHTML = '';
    allEndpoints = [];

    for (const tag of tagOrder) {
      const section = document.createElement('div');
      section.className = 'content-section';
      section.id = 'tag-' + tag;
      section.innerHTML = '<div class="section-header"><h2>' + esc(tag) + '</h2><span class="count">' + tagMap[tag].length + '</span></div>';

      tagMap[tag].forEach(ep => {
        const card = document.createElement('div');
        card.className = 'ep-card';
        card.dataset.tag = tag;
        card.dataset.search = (tag + ' ' + ep.path + ' ' + (ep.summary || '') + ' ' + (ep.description || '')).toLowerCase();

        const methodClass = 'm-' + ep.method.toLowerCase();
        const summary = ep.summary || '';

        card.innerHTML =
          '<div class="ep-card-header" onclick="toggleCard(this)">' +
            '<span class="ep-chevron">&#9654;</span>' +
            '<span class="ep-method ' + methodClass + '">' + ep.method + '</span>' +
            '<span class="ep-path">' + esc(ep.path) +
              (ep.deprecated ? ' <span class="ep-deprecated">deprecated</span>' : '') +
            '</span>' +
            (summary ? '<span class="ep-summary">' + esc(summary) + '</span>' : '') +
            '<button class="ep-copy" title="Copy path" onclick="event.stopPropagation(); copyPath(this,\'' + esc(ep.path) + '\')">&#128203;</button>' +
          '</div>' +
          '<div class="ep-body">' +
            '<div class="ep-body-inner">' +
              buildDetail(ep, comps) +
            '</div>' +
          '</div>';

        section.appendChild(card);
        allEndpoints.push({ tag, el: card, ep });
      });

      content.appendChild(section);
    }
  }

  // ── Toggle card ──
  window.toggleCard = function(header) {
    const body = header.nextElementSibling;
    const chevron = header.querySelector('.ep-chevron');
    const isOpen = body.classList.contains('open');
    body.classList.toggle('open');
    if (chevron) chevron.classList.toggle('open');
  };

  // ── Expand / collapse all ──
  window.expandAll = function() {
    document.querySelectorAll('.ep-body').forEach(b => b.classList.add('open'));
    document.querySelectorAll('.ep-chevron').forEach(c => c.classList.add('open'));
  };
  window.collapseAll = function() {
    document.querySelectorAll('.ep-body').forEach(b => b.classList.remove('open'));
    document.querySelectorAll('.ep-chevron').forEach(c => c.classList.remove('open'));
  };

  // ── Copy path ──
  window.copyPath = function(btn, path) {
    navigator.clipboard.writeText(path).then(() => {
      btn.textContent = '\u2713';
      setTimeout(() => { btn.textContent = '\uD83D\uDCCB'; }, 1500);
    });
  };

  // ── Copy cURL ──
  window.copyText = function(btn, text) {
    const unescaped = text.replace(/\\'/g, "'");
    navigator.clipboard.writeText(unescaped).then(() => {
      const orig = btn.textContent;
      btn.textContent = 'Copied!';
      setTimeout(() => { btn.textContent = orig; }, 2000);
    });
  };

  // ── Search ──
  let searchDebounce = null;
  window.onSearch = function(value) {
    clearTimeout(searchDebounce);
    searchDebounce = setTimeout(() => {
      const q = value.trim().toLowerCase();
      document.querySelectorAll('.ep-card').forEach(card => {
        const text = card.dataset.search || '';
        card.style.display = (!q || text.includes(q)) ? '' : 'none';
      });
      document.querySelectorAll('.content-section').forEach(section => {
        const visible = section.querySelectorAll('.ep-card[style*="display: none"]').length === 0;
        section.style.display = visible ? '' : 'none';
      });
    }, 150);
  };

  // ── Sidebar toggle (mobile) ──
  window.toggleSidebar = function() {
    document.getElementById('sidebar').classList.toggle('open');
  };
  window.closeSidebar = function() {
    document.getElementById('sidebar').classList.remove('open');
  };

  // ── Fetch and render ──
  fetch('/openapi.json')
    .then(resp => {
      if (!resp.ok) throw new Error('HTTP ' + resp.status);
      return resp.json();
    })
    .then(spec => { render(spec); })
    .catch(err => {
      document.getElementById('content').innerHTML =
        '<div class="error"><strong>Failed to load API specification</strong><p>' + esc(err.message) + '</p></div>';
    });
})();
</script>
</body>
</html>
"""


def get_redoc_html() -> str:
    return REDOC_HTML


def get_swagger_ui_html() -> str:
    return SWAGGER_UI_HTML
