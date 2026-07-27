# Training Operations Center v6.12 — OpenID Connect Edition

This build adds OIDC Authorization Code Flow while preserving the existing training features and an optional local-login fallback.

## Environment-specific values to change

Change the following in  '.env' to match your specific settings:

1. `TOC_FRONTEND_URL` — the externally reachable app URL, for example `https://training.company.com`.
2. `TOC_COOKIE_SECURE` — set `true` when the app uses HTTPS.
3. `TOC_OIDC_PROVIDER_NAME` — text shown on the login button.
4. `TOC_OIDC_CLIENT_ID` and `TOC_OIDC_CLIENT_SECRET` — from the IdP application registration.
5. `TOC_OIDC_DISCOVERY_URL` — the provider's OpenID configuration URL.
6. `TOC_OIDC_ISSUER` — the exact issuer value used by the provider.
7. `TOC_OIDC_REDIRECT_URI` — normally `https://training.company.com/api/auth/oidc/callback`.
8. `TOC_OIDC_LOGOUT_URL` — optional provider end-session URL.
9. Admin/instructor email or group mappings.
10. Generate strong independent values for `TOC_SECRET_KEY` and `TOC_SESSION_SECRET`.

## Identity-provider application registration

Register a **Web application** (confidential client), not a SPA client.

Redirect URI:

`https://training.company.com/api/auth/oidc/callback`

Scopes:

`openid profile email`

If you want group-based roles, configure the IdP to include a `groups` claim in the ID token/userinfo response.

## Start locally

```bash
# Edit .env
docker compose up --build
```

Open `http://localhost:3000`.

## Production settings

- Put the site behind HTTPS.
- Set `TOC_COOKIE_SECURE=true`.
- Set `TOC_LOCAL_LOGIN_ENABLED=false` after OIDC is proven.
- Set `TOC_RESET_DEFAULT_ADMIN=false` and `TOC_ENABLE_BOOTSTRAP_RESET=false`.
- Keep secrets outside source control.
- Back up the Docker volume or move to PostgreSQL for a production deployment.

## Provisioning behavior

The app identifies OIDC users using issuer + subject. On first login it can automatically create a local account. Local app roles remain in the app database. Admin role can be assigned using `TOC_OIDC_ADMIN_EMAILS` or `TOC_OIDC_ADMIN_GROUPS`.
