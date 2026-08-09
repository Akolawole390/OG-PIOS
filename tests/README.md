# Tests

Unit tests currently live alongside their own stack:
- Backend: `backend/tests/` (pytest, in-memory SQLite).
- Frontend: `frontend/src/**/__tests__/` (Vitest + React Testing Library).

This top-level folder is reserved for **future cross-stack/end-to-end tests** (e.g.
Playwright driving the real frontend against the real Docker-Compose backend) — nothing here
yet.
