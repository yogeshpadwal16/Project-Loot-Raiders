# PWA Frontend & Performance Guidelines Skill

This skill defines UI/UX design standards and performance optimization guidelines for the **Loot Raiders Web Dashboard / PWA** (`dashboard/`, `web/server.py`).

---

## 1. Design Tokens & Visual Hierarchy

- **Color Palette**: Dark theme base (`#0f172a`, `#1e293b`), vibrant accents (Loot Orange `#f97316`, Verified Green `#22c55e`).
- **Typography**: Google Fonts Inter / Outfit for modern readability.
- **Responsiveness**: Flexbox/Grid layouts optimized for mobile PWA viewports without horizontal scrolling.

---

## 2. Performance & Asset Guidelines

- **Zero Heavy Frameworks**: Dashboard utilizes Vanilla HTML5, CSS3, and ES6 JavaScript to ensure sub-100ms render times.
- **Asset Load Optimization**: Serve static assets (`index.css`, `index.js`) with proper MIME types and caching headers via `web/server.py`.
- **SSE Stream Efficiency**: Server-Sent Events (`/api/deals/stream`) must handle disconnections gracefully without blocking server worker threads.
