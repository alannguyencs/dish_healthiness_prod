# Authentication

[Parent](./index.md) | [Next: Calendar Dashboard >](./calendar_dashboard.md)

**Status:** Done

## Related Docs
- Technical: [technical/authentication.md](../technical/authentication.md)

## Problem

The application stores personal meal history and nutritional insights tied to a specific user. We need a way to keep each user's data private and let returning users pick up where they left off without signing in every visit.

## Solution

Users sign in with a username and password. Once signed in, the application remembers the user for up to 90 days on that device, so they go straight to their calendar on every return visit. Users can sign out at any time to end the session.

## User Flow

```
Visit app
  |
  v
Already signed in? --Yes--> Go to Calendar Dashboard
  |
  No
  |
  v
Login page (username + password)
  |
  v
Submit --Invalid--> Show error, stay on login
  |
  Valid
  |
  v
Session created (90 days)
  |
  v
Go to Calendar Dashboard
  |
  v
(At any time) Click "Logout" --> Session cleared --> Return to Login page
```

## Scope

- **Included:**
  - Sign in with username and password
  - Stay signed in for 90 days after a successful login
  - Sign out from any page that shows the header
  - Block access to meal pages when not signed in (redirect to login)
- **Not included:**
  - Self-service signup (accounts are provisioned by an administrator)
  - Password reset flow
  - Email verification or multi-factor authentication
  - Third-party providers (Google, Apple, etc.)

## Acceptance Criteria

- [x] A user with valid credentials can sign in and lands on the Calendar Dashboard
- [x] A user with invalid credentials stays on the login page and sees an error message
- [x] A signed-in user who closes the browser and returns within 90 days is taken straight to the dashboard
- [x] Clicking "Logout" returns the user to the login page and requires re-entering credentials
- [x] Visiting any protected page while signed out redirects to the login page

---

[Parent](./index.md) | [Next: Calendar Dashboard >](./calendar_dashboard.md)
