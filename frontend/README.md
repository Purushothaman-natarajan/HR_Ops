# Frontend — Self-Healing HR Ops Platform

React 18 + TypeScript + Vite frontend for the HR Ops multi-agent platform.

## Quick Start

```bash
npm install
npm run dev        # Dev server on :5173, proxies API to :8000
npm run build      # Production build to dist/
```

## Project Structure

```
src/
├── api/
│   └── client.ts          # All API methods (health, graph, conversation, policies, feedback, RL, etc.)
├── components/
│   ├── ChatInterface.tsx   # Multi-turn chat with inline ratings
│   ├── PolicyManager.tsx   # Policy CRUD with upload modal + markdown preview
│   ├── HITLPanel.tsx       # AG-UI human-in-the-loop approval interface
│   ├── Sidebar.tsx         # Dark sidebar with role-based section filtering
│   ├── Dashboard.tsx       # Home dashboard with navigation cards
│   ├── TraceViewer.tsx     # Execution trace display
│   ├── TraceQueryPanel.tsx # Search/filter/compare traces
│   ├── RLDashboard.tsx     # RL diagnostics + feedback stats
│   ├── CostDashboard.tsx   # Cost breakdown charts
│   └── StatusIndicator.tsx # Health dot + run count (top-right of every page)
├── types/
│   └── index.ts            # TypeScript interfaces (GraphRunResponse, ConversationSession, etc.)
├── App.tsx                 # Root component: sidebar routing + role-based gating
├── App.css                 # Component-specific styles
├── index.css               # Design system: CSS custom properties + base reset
└── main.tsx                # React entry point
```

## Component Tree

```
<App>                              ← role fetch from /health on mount
  <StatusIndicator />              ← top-right: health dot + run count (always visible)
  <Sidebar />                      ← shows sections based on role
  <main>                           ← content area
    └── {activePage}              ← role-gated page switching
         ├── Dashboard             ← overview cards, navigates to sections
         ├── ChatInterface         ← multi-turn conversation + mode selector
         ├── PolicyManager         ← split-pane: list + preview, upload modal
         ├── HITLPanel             ← pending HITL requests, approve/deny
         ├── TraceViewer           ← trace event timeline
         ├── TraceQueryPanel       ← search + compare traces
         ├── RLDashboard           ← RL arm stats + feedback stats
         └── CostDashboard         ← cost breakdown
```

## Data Flow

```
User action → Page component → api.client.method() → HTTP fetch → FastAPI backend
                                                              ↓
User sees   ← Page component ← JSON response deserialized  ← response
```

State is local per component or passed via props. No global state store is used (the `store/` and `hooks/` directories are available for future expansion).

## CSS Design System

All styles use CSS custom properties defined in `src/index.css`:

| Category | Example Variables |
|----------|------------------|
| Colors | `--color-primary: #6366f1`, `--color-sidebar: #0f172a`, `--color-bg: #f1f5f9` |
| Surfaces | `--color-surface: #ffffff`, `--color-bg: #f1f5f9` |
| Text | `--color-text: #0f172a`, `--color-text-secondary: #475569` |
| Borders | `--color-border: #e2e8f0`, `--radius: 8px` |
| Shadows | `--shadow-sm`, `--shadow`, `--shadow-lg` |
| Layout | `--sidebar-width: 240px` |
| Typography | `--font-family: Inter, sans-serif`, `--font-mono: JetBrains Mono, monospace` |

### Layout Classes (in `App.css`)
- `.app-layout` — flexbox row with sidebar + main content
- `.app-main` — scrollable content area
- `.app-content` — padded content wrapper
- `.page-header` / `.page-title` / `.page-desc` — page headings
- `.card` / `.card-header` / `.card-body` — reusable card component
- `.btn` / `.btn-primary` / `.btn-danger` / `.btn-sm` — button variants
- `.badge` / `.badge-success` / `.badge-warning` / `.badge-error` / `.badge-info` — status badges
- `.empty-state` — centered empty-state placeholder

## Role-Based Access

Roles are fetched from `GET /health` on mount:

```typescript
const [role, setRole] = useState<AppRole>("admin");

useEffect(() => {
  api.health().then((r) => setRole(r.data.role));
}, []);
```

- **Admin**: Full access — all sections, policy edit/delete
- **User**: Cannot see Trace, TraceQuery, RL Dashboard, or Cost Dashboard. Policy Manager is view-only with info banner.

### Adding Role-Gated Content
```typescript
if (role === "user") return <AccessDenied />;
```

The Sidebar uses `roleConfig.sections` from the API to decide which nav items to render. Policy Manager receives `role` as a prop and toggles edit controls.

## How to Add a New Page

1. Create a component in `src/components/` (e.g., `Reports.tsx`)
2. Add the page to the `Page` type in `src/App.tsx`:
   ```typescript
   type Page = "dashboard" | "query" | ... | "reports";
   ```
3. Add a `case` in `renderPage()` in `App.tsx`
4. Add a nav item in `Sidebar.tsx`
5. If role-gated:
   ```typescript
   case "reports":
     if (role === "user") return <AccessDenied />;
     return <Reports />;
   ```

## How to Add a New API Method

In `src/api/client.ts`:

```typescript
export const api = {
  // ...
  reports: {
    list: () => request<APIResponse<{ reports: Report[] }>>("/reports"),
    get: (id: string) => request<APIResponse<Report>>(`/reports/${id}`),
  },
};
```

Add corresponding types in `src/types/index.ts`.

## API Proxy Configuration

In `vite.config.ts`, the dev server proxies all API paths to `localhost:8000`:

```typescript
server: {
  proxy: {
    "/health": "http://localhost:8000",
    "/graph": "http://localhost:8000",
    "/conversation": "http://localhost:8000",
    "/policies": "http://localhost:8000",
    "/feedback": "http://localhost:8000",
    "/agui": "http://localhost:8000",
    "/trace": "http://localhost:8000",
    "/debug": "http://localhost:8000",
    "/rl": "http://localhost:8000",
    "/docs": "http://localhost:8000",
    "/openapi.json": "http://localhost:8000",
  },
},
```

## Key Dependencies

| Package | Use |
|---------|-----|
| `react 18` | UI framework |
| `react-markdown` | Policy content rendering |
| `recharts` | RL/Cost dashboard charts |

## Troubleshooting

| Problem | Fix |
|---------|-----|
| API calls return 404 | Ensure backend is running on :8000 |
| CORS errors in dev | Vite proxies all requests — ensure you're accessing `localhost:5173` not `localhost:8000` |
| Policy upload fails | Check file is PDF, MD, or TXT; ensure role is "admin" |
| RL dashboard shows no data | Submit some feedback ratings via ChatInterface first |
