# Authentication — Technical Design

[< Prev: System Pipelines](./system_pipelines.md) | [Parent](./index.md) | [Next: Calendar Dashboard >](./calendar_dashboard.md)

## Related Docs
- Abstract: [abstract/authentication.md](../abstract/authentication.md)

## Architecture

Stateless JWT session carried in an HTTP-only cookie. The frontend never sees the token; every authenticated request sends the cookie back automatically (`withCredentials: true` on the axios client), and the backend decodes it per request.

```
+---------------------+        +---------------------+        +------------------+
|   React SPA         |        |   FastAPI           |        |   Postgres       |
|                     |        |                     |        |                  |
|  Login.jsx          |        |  /api/login/        |        |  users           |
|  AuthContext        |        |  /api/login/logout  |        |  (id, username,  |
|  ProtectedRoute     |        |  authenticate_user_ |        |   hashed_password|
|                     |<======>|  from_request()     |<------>|   role)          |
|                     |cookie  |                     | ORM    |                  |
+---------------------+        +---------------------+        +------------------+
                                     │
                                     ▼
                               +----------------+
                               | python-jose    |
                               | HS256, 90-day  |
                               | JWT_SECRET_KEY |
                               +----------------+
```

## Data Model

**`Users`** (table `users`) — `backend/src/models.py`

| Column | Type | Constraints |
|--------|------|-------------|
| `id` | Integer | PK, indexed |
| `username` | String | NOT NULL, UNIQUE |
| `hashed_password` | String | NOT NULL (bcrypt) |
| `role` | String | nullable, default `None` |

Passwords are stored as bcrypt hashes via `passlib.context.CryptContext(schemes=["bcrypt"])`. No plaintext passwords are ever persisted.

## Pipeline

```
Login.jsx: submit {username, password}
  │
  ▼
AuthContext.login() → apiService.login()
  │
  ▼
POST /api/login/
  │
  ▼
api/login.py: process_login(LoginRequest)
  │
  ▼
auth.py: authenticate_user(username, password)
  │
  ├──> crud_user.get_user_by_username()  ──> Users row
  │
  └──> bcrypt_context.verify(password, user.hashed_password)
  │
  ▼
auth.py: create_access_token({username}) → JWT (HS256, 90 d)
  │
  ▼
JSONResponse.set_cookie(
    key="access_token",
    httponly=True, samesite="lax", secure=False,
    max_age=7776000, path="/")
  │
  ▼
AuthProvider: setUser / setAuthenticated(true)
  │
  ▼
<Navigate to="/dashboard" />

---- On subsequent requests ----

Any protected API route
  │
  ▼
auth.py: authenticate_user_from_request(request)
  │
  ├──> request.cookies.get("access_token")
  │
  ▼
auth.py: get_current_user_from_token(token)
  │
  ├──> jwt.decode(token, SECRET_KEY, algorithms=[HS256])
  │
  └──> crud_user.get_user_by_username(payload["username"])
  │
  ▼
Return Users, or False (route raises HTTPException 401)
```

## Algorithms

### Password verification

- Bcrypt `verify` compares the submitted plaintext against the stored hash in constant time.
- `authenticate_user` returns the `Users` object on match, `False` on any failure (unknown username or mismatch).

### Token encoding

- Payload: `{"username": <str>, "expire": <iso datetime>}`.
- Algorithm: HS256. Secret from `JWT_SECRET_KEY` env var.
- Default TTL: 90 days (`timedelta(days=90)`), matching the cookie `max_age=7776000`.

### Token decoding

- `jwt.decode(token, SECRET_KEY, algorithms=["HS256"])`.
- Any `JWTError` → return `None` (the caller treats `None` as unauthenticated).
- The token's `expire` field is informational; cookie `max_age` is the actual expiry boundary enforced by the browser.

## Backend — API Layer

| Method | Path | Auth | Request | Response | Status |
|--------|------|------|---------|----------|--------|
| POST | `/api/login/` | — | `{username, password}` | `{success, message, user: {id, username}}` + `Set-Cookie: access_token` | 200 / 401 |
| POST | `/api/login/logout` | — | — | `{success, message}` + `Delete-Cookie: access_token` | 200 |

All other protected routes call `authenticate_user_from_request(request)` at the top of the handler and raise `HTTPException(401, "Not authenticated")` on failure.

## Backend — Service Layer

- `src/auth.py` owns token generation (`create_access_token`), token decoding (`get_current_user_from_token`), and cookie-based request auth (`authenticate_user_from_request`).
- `src/crud/crud_user.py` owns `Users` lookups (`get_user_by_username`, `get_user_by_id`).
- `bcrypt_context = CryptContext(schemes=["bcrypt"], deprecated="auto")` is module-level and shared across the process.

## Backend — CRUD Layer

- `get_user_by_username(username)` — single-row fetch by unique username.
- `get_user_by_id(user_id)` — used by admin paths (not login).
- `create_user(username, hashed_password, role)` — used only for administrative account provisioning; there is no self-signup route exposed by the API.

## Frontend — Pages & Routes

| Route | Page | Protection |
|-------|------|------------|
| `/login` | `Login.jsx` | Public |
| `/dashboard` | `Dashboard.jsx` | `ProtectedRoute` |
| `/date/:year/:month/:day` | `DateView.jsx` | `ProtectedRoute` |
| `/item/:recordId` | `ItemV2.jsx` | `ProtectedRoute` |
| `/reference/serving-size` | `ServingSizeReference.jsx` | Public |
| `/` | `RedirectToDashboard` | Redirects based on `useAuth().authenticated` |

## Frontend — Components

- `contexts/AuthContext.js` — `AuthProvider` holds `{user, authenticated, loading, login, logout}`. Exposed via `useAuth()` hook.
- `components/ProtectedRoute.jsx` — wraps children with an auth check; shows a loading state while `loading===true`, redirects to `/login` when unauthenticated.

Auth state currently lives only in memory on the React side; on a hard refresh the `AuthProvider` initializes with `authenticated=false` and the user is bounced to `/login` — the server-side cookie is still valid, but the SPA does not call a session-verification endpoint at mount time. Login via the existing cookie is effectively refreshed by a successful API call on any page; however a direct refresh on a protected page sends the user through login again.

## Frontend — Services & Hooks

- `services/api.js` — axios instance with `baseURL = REACT_APP_API_URL || http://localhost:2612` and `withCredentials: true` so the browser always attaches the `access_token` cookie.
- `apiService.login(username, password)` → `POST /api/login/`.
- `apiService.logout()` → `POST /api/login/logout`.

## External Integrations

None. JWT signing and bcrypt hashing are done in-process.

## Constraints & Edge Cases

- `JWT_SECRET_KEY` must be set in the backend environment; unset secret will cause `jwt.encode` / `jwt.decode` to fail and all auth to return `False`.
- `secure=False` on the cookie means the cookie is accepted over plain HTTP in development. Production deployments behind HTTPS should flip this to `True`.
- CORS allowed origins come from the `ALLOWED_ORIGINS` env var (default `http://localhost:2512`). When set to `"*"`, `allow_credentials` is forced to `False` and the cookie-based flow stops working.
- SessionMiddleware in `main.py` is initialized with a placeholder secret key that should be replaced before production.
- A hard browser refresh loses in-memory React auth state; user is sent to `/login` even while the backend cookie is still valid.
- No refresh token is issued; once the 90-day TTL elapses the user must re-authenticate.

## Component Checklist

- [x] `users` table — `username` unique, bcrypt `hashed_password`, optional `role`
- [x] `authenticate_user(username, password)` — username lookup + bcrypt verify
- [x] `create_access_token({username})` — HS256 JWT, 90-day expiry
- [x] `get_current_user_from_token(token)` — JWT decode + username lookup
- [x] `authenticate_user_from_request(request)` — reads `access_token` cookie
- [x] `POST /api/login/` — sets HttpOnly SameSite=Lax cookie
- [x] `POST /api/login/logout` — clears the cookie
- [x] `AuthProvider` / `useAuth()` — React state + login / logout actions
- [x] `ProtectedRoute` — gates dashboard, date view, item view
- [x] `RedirectToDashboard` — root-path routing based on auth state

---

[< Prev: System Pipelines](./system_pipelines.md) | [Parent](./index.md) | [Next: Calendar Dashboard >](./calendar_dashboard.md)
