# Auth-Gated App Testing Playbook (Emergent Google Auth)

This app uses Emergent-managed Google OAuth. There are NO app-managed passwords.
To test auth-gated pages, seed a session token directly in Mongo and use it as a
cookie (browser) or Bearer token (API).

## Seed a test user + session
```
mongosh --quiet --eval '
const db = db.getSiblingDB("test_database");
const uid = "user_testabc123";
const tok = "test_session_token_123";
db.users.deleteMany({user_id: uid});
db.user_sessions.deleteMany({user_id: uid});
db.users.insertOne({user_id: uid, email: "tester@example.com", name: "Test Tester", picture: "https://via.placeholder.com/64", created_at: new Date().toISOString()});
db.user_sessions.insertOne({user_id: uid, session_token: tok, expires_at: new Date(Date.now()+7*24*3600*1000), created_at: new Date()});
'
```

## Backend API (Bearer)
```
curl -H "Authorization: Bearer test_session_token_123" https://<host>/api/auth/me
curl -H "Authorization: Bearer test_session_token_123" https://<host>/api/projects
```

## Browser (cookie)
```
await page.context.add_cookies([{
  "name": "session_token", "value": "test_session_token_123",
  "url": "https://<host>", "httpOnly": True, "secure": True, "sameSite": "None"
}])
await page.goto("https://<host>/dashboard")
```

## Notes
- Cookie is httpOnly + secure + SameSite=None; backend reads cookie first, then Bearer.
- Session expiry is 7 days, timezone-aware.
- The screenshot tool wraps the script in `run_test(page, ...)`; write TOP-LEVEL
  statements using `page` (do NOT define your own `def run`).
