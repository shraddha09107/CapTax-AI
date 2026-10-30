# CapTax AI — Landing Site + Auth + Protected App Plan

## Stack (existing, unchanged)
- **Frontend**: Pure HTML5 + CSS Custom Properties + Vanilla ES6+. No bundler.
- **Backend**: FastAPI (Python 3.10), pandas, uvicorn. Port 8001.
- **Charts**: SVG built by DOM manipulation (no external chart lib).
- **Theme**: Single tokens file at `frontend/styles/theme.css`. localStorage key `captax-theme`.

## Routes

| Path | Public? | File served | Notes |
|---|---|---|---|
| `/` | ✅ Public | `frontend/landing.html` | 3D coin hero, marketing sections |
| `/login` | ✅ Public | `frontend/login.html` | Split layout, auth form |
| `/app` | 🔒 Protected | `frontend/index.html` | Dashboard — redirects to `/login?next=/app` if no session |
| `/app/*` | 🔒 Protected | `frontend/index.html` | All dashboard sub-pages |
| `404` | - | `frontend/404.html` | Themed 404 |

## Auth Approach

### Backend
- `POST /auth/login` — accepts `{id, password}` JSON, issues a **signed session cookie** (`httpOnly`, `SameSite=lax`) via `itsdangerous.TimestampSigner`. No JWT. Cookie name: `captax_session`. TTL: 8 hours.
- `POST /auth/logout` — clears the cookie.
- `GET /auth/me` — returns `{id, authenticated: true}` if valid session, else 401.
- All `/data/*` and `/pipeline/*` routes protected by a `require_auth` dependency.
- Rate-limit: in-memory dict, 5 failed attempts → 60 s lockout per ID.
- Dev seed: env vars `ADMIN_ID` (default `admin`) and `ADMIN_PASSWORD_HASH` (pre-generated bcrypt hash of `@Admin123`).

### Frontend
- On every page load, call `GET /auth/me` with `credentials: 'include'`.
- If 401 and on `/app*` → redirect to `/login?next=<path>`.
- If on `/login` and authenticated → redirect to `?next` or `/app`.
- 401 from any API call during app usage → clear local state, toast "Session expired", redirect to `/login?next=`.
- All fetch calls use `credentials: 'include'`.

## Files Created / Modified

### New files
```
frontend/landing.html          Public landing page (3D coins, marketing)
frontend/login.html            Login split-layout page
frontend/404.html              Themed 404
frontend/js/auth.js            Auth client utility (me, login, logout, guard)
frontend/js/three-coins.js     WebGL 3D coin scene (Three.js CDN, lazy-loaded)
scripts/verify_pipeline.sh     Pre/post auth pipeline regression script
```

### Modified files
```
backend/app.py                 Add /auth/* endpoints, auth middleware, CORS creds
backend/requirements.txt       Add passlib, bcrypt, python-multipart, itsdangerous
frontend/styles/theme.css      Add --brand-name, --profit, --loss, --neutral tokens
frontend/index.html            Add auth guard, credentials on all fetch calls
```

## Global Colour Semantics (new tokens)
```css
--brand-name: #4DA3FF (dark) / #1F6FEB (light)  — ticker/broker/company names
--profit:     #3DDC97 (dark) / #12A150 (light)   — gains, dividends received, credits
--loss:       #FF4D5E (dark) / #D93025 (light)   — losses, negative values
--neutral:    #FFFFFF (dark) / #15151A (light)   — zero/info values
```

## Regression Gate
`scripts/verify_pipeline.sh`:
1. Hits `/pipeline/run` without auth → expects 401.
2. Logs in as `admin / @Admin123` → captures session cookie.
3. Hits `/pipeline/run` with cookie → expects 200, all 7 steps.
4. Hits `/data/tax-summary` → captures Schedule CG rows.
5. Hits `/data/dtaa-relief` → captures FSI row count.
6. Compares output hashes to baseline saved before auth.

## Code-split guarantee
- `/` loads only `landing.html` + `three-coins.js` (lazy, dynamic import).
- `/login` loads only `login.html` + `auth.js`.
- `/app` loads `index.html` + `auth.js` (guard check). Three.js never loads on `/app`.
- No shared bundle — each page is a standalone HTML file with its own `<script>` tags.

## Performance targets
- Landing hero: DPR capped at 1.5, render loop paused via `document.hidden`, IntersectionObserver for off-screen.
- Mobile: coin count reduced from 12 → 4.
- `prefers-reduced-motion`: static CSS poster instead of WebGL.
- WebGL failure: CSS-3D coin fallback.
- Text content never blocked on 3D load (hero content renders immediately, canvas fades in).

