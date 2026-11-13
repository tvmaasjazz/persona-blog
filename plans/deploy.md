# Deploy — plan

Personagora runs on Railway in two environments: staging, then production. This plan
covers where each piece lives, how traffic reaches it, and the steps to stand staging
up. Production repeats the same steps with its own branch, domains and secrets.
`plan.md` › Phase 1 › 12 lists what the app itself needs before a deploy, and 13 lists
the first-deploy checks.

## Environments

|                 | Staging                       | Production                 |
| --------------- | ----------------------------- | -------------------------- |
| Deploys from    | `main`, after CI passes       | `production`               |
| Frontend        | `staging.personagora.com`     | `personagora.com`          |
| API             | `api-staging.personagora.com` | `api.personagora.com`      |
| `ENVIRONMENT`   | `STAGING`                     | `PRODUCTION`               |
| Database        | its own, starts empty         | its own                    |

- **Staging redeploys on every merge to `main`,** once GitHub CI passes (Railway's
  "Wait for CI"). A build or migration that breaks shows up there before a release.
- **A release merges `main` into `production`.** Nothing else merges into it.
- **`STAGING` behaves like `PRODUCTION`** everywhere the code checks the environment:
  secure cookies, Redis database 0 for the graph checkpointer, and the dev-only
  scripts refusing to run. It exists so staging can differ later without a deploy
  pretending to be production.

## Railway

One project, `personagora`, in the personal workspace (Tyler Vander Maas's Projects),
not Brownfield AI. It has two environments, `staging` and `production`, and each has
the same four services:

| Service    | Source                               | Public domain        |
| ---------- | ------------------------------------ | -------------------- |
| `web`      | `frontend/`, a Dockerfile            | the frontend's       |
| `api`      | `backend/`, a Dockerfile             | the API's            |
| `Postgres` | Railway's Postgres                   | none                 |
| `Redis`    | an image with Redis 8 and a volume   | none                 |

- **Each service builds only when its own folder changes,** using watch paths:
  `/frontend/**` for `web`, `/backend/**` for `api`.
- **Each service's root directory is its folder,** `backend/` or `frontend/`, and it
  builds from the Dockerfile there.
- **`.railway/railway.ts` defines every environment:** services, settings, replicas,
  domains and variables, with what differs between environments in one table at its
  top. Railway applies it only when told to:
  - Change the file, then `railway config plan --environment <name>` from
    `.railway/`, then `railway config apply --environment <name>`. Node 22.6 or later
    runs it (`.railway/.nvmrc`).
  - It owns the variables: one missing from a service is deleted on apply. A secret is
    set in the dashboard and listed as `preserve()`, so its value never enters the repo.
  - A change made in the dashboard is undone by the next apply, unless it's added to
    the file first.
  - Railway can't register a custom domain from the file, only keep one: a new domain
    is added with `railway domain`, then switched on in the file.
- **Redis must be version 8 or later,** since the graph checkpointer uses its search
  module (`lifespan.py`). Railway's Redis template is 8.2.
- **Postgres** only needs the `citext` extension, which the migrations create.

### How the browser reaches the API

The browser only ever talks to the frontend's domain. `web` serves the built app and
forwards `/api/*` to `api` over Railway's private network, removing the `/api`
prefix. That's what Vite's proxy does in development, so the frontend's code is the
same in every environment.

- **No CORS and no API URL in the frontend build.** The session cookie is set on the
  frontend's domain, so it's first-party wherever the user's browser is.
- **`api`'s public domain is for checks, not the browser:** `/health`, the
  `backend/scripts/e2e/` scripts, and the API docs. A request there carries no session
  cookie, since that cookie belongs to the frontend's domain.
- **`web` is Caddy** (`frontend/Caddyfile`) serving `dist/`, with any path that isn't
  a file answered by `index.html`, and `/api/*` forwarded to `API_UPSTREAM`.
- **The client's IP comes through Cloudflare** (`USERS__CLIENT_IP_SOURCE=CLOUDFLARE`,
  read by `ClientIpUtils`). Railway's edge sets `X-Real-IP` to whatever connected to
  it, which is a Cloudflare server, and Cloudflare sets `CF-Connecting-IP` to the
  client. Caddy passes both through untouched.
  - `CF-Connecting-IP` is trusted only when `X-Real-IP` is in Cloudflare's published
    ranges (`libs/users/constants.py`). Anyone can send the header, so a request that
    went around Cloudflare to Railway's edge keeps the address it really came from.
  - The `cloudflare-ips` workflow compares the constant with Cloudflare's API every
    Monday and fails, which emails Tyler, when they differ; its output says which
    ranges to add and remove. A missing range makes those visitors look like
    Cloudflare's address, never lets anyone choose their own.
  - `/health` returns the IP the API resolved, to check this on a deploy.
- **`api` listens on `::`,** so it answers on the private network whether that runs
  over IPv6 or IPv4.

### `api`

- **Start:** granian in exec form, configured by `GRANIAN_*` variables in the
  Dockerfile, any of which a Railway variable overrides.
- **Scaled by instances, not workers:** one granian worker per instance, and two
  instances (`numReplicas`) in every environment, so staging runs the same
  cross-process paths (run handoff, lease pickup) production does, and a redeploy or
  a crashed instance leaves the other serving.
- **Port 8000, fixed.** Exec form can't expand `$PORT`, so `PORT` is set to 8000 in
  Railway, which routes and health-checks on it.
- **Pre-deploy:** `alembic upgrade head`. A migration that fails stops the deploy.
- **Health check:** `/health`.

### Variables

Set per environment in `.railway/railway.ts`. The secrets (`GOOGLE_CLIENT_ID`,
`GOOGLE_CLIENT_SECRET`, `OPENAI_API_KEY`) are set in the dashboard and are
`preserve()` in the file.

| Variable                    | Staging                                                         |
| --------------------------- | --------------------------------------------------------------- |
| `ENVIRONMENT`               | `STAGING`                                                       |
| `PORT`                      | `8000`                                                          |
| `USERS__CLIENT_IP_SOURCE`   | `CLOUDFLARE`                                                    |
| `DATABASE_URL`              | `postgresql+asyncpg://` built from the Postgres service's `PGUSER`, `PGPASSWORD`, `PGHOST`, `PGPORT` and `PGDATABASE`. Railway's own `DATABASE_URL` uses the `postgresql://` scheme, which asyncpg won't take |
| `REDIS_URL`                 | Redis's private URL, database 0                                 |
| `GOOGLE_CLIENT_ID`          | the staging OAuth client's                                      |
| `GOOGLE_CLIENT_SECRET`      | the staging OAuth client's                                      |
| `GOOGLE_AUTH__REDIRECT_URL` | `https://staging.personagora.com/api/auth/google/callback`      |
| `AUTH__FRONTEND_URL`        | `https://staging.personagora.com`                               |
| `OPENAI_API_KEY`            | a key for staging, so its usage shows apart                     |

`web` gets `API_UPSTREAM=${{api.RAILWAY_PRIVATE_DOMAIN}}:${{api.PORT}}`, and `PORT`
fixed at 8080 so its domain has a known target port.

LaunchDarkly adds `LAUNCHDARKLY_SDK_KEY` and `LAUNCHDARKLY__IS_ENABLED` when it lands
(`launchdarkly-agentcontrol.md`), with a LaunchDarkly environment per Railway one.

## Google sign-in

One Google Cloud project, Personagora, with an OAuth client for each environment.

- **The consent screen is set up once,** for the project: the app's name, the support
  email, and `personagora.com` as an authorized domain. The app asks only for
  `openid`, `email` and `profile`, which need no Google review. Its publishing status
  must be **In production**; while it's in Testing, only the listed test users can sign
  in.
- **Each client is a Web application** with one authorized redirect URI, the frontend
  domain's `/api/auth/google/callback`:
  - staging: `https://staging.personagora.com/api/auth/google/callback`
  - production: `https://personagora.com/api/auth/google/callback`
- **The redirect goes through the frontend's domain, not the API's,** so the session
  cookie the callback sets lands on the domain the browser uses. A callback to
  `api-staging.` would set the cookie there, and the app would never send it.
- **Separate clients keep the secrets apart,** so a staging secret that leaks can't
  sign anyone in to production.

## DNS

Cloudflare's free plan serves `personagora.com`. Namecheap stays the registrar.

1. Add `personagora.com` to Cloudflare, check it copied every record, then change the
   nameservers in Namecheap to the two Cloudflare gives.
2. For each custom domain added in Railway, add the CNAME and TXT records Railway
   shows. A CNAME on the bare domain works, since Cloudflare flattens it.
3. Railway's CNAMEs are **proxied** (orange cloud) from the moment they're added, so
   the Railway target never appears in public DNS history. Its TXT records can't be.
4. Cloudflare's settings:
   - **SSL/TLS: Full.** Railway may not issue a certificate for a proxied domain and
     answers with its `*.up.railway.app` one, which Full (strict) rejects. Flexible
     loops redirects.
   - **Always Use HTTPS: on.**
   - **Bot Fight Mode: off.** It blocks scripts and `curl`, so checks against the API
     would fail.
   - **Caching: the defaults.** Cloudflare caches the built assets, which Caddy marks
     immutable, and never HTML or API responses.

### Email

No email uses the domain yet. When it does, each kind is added separately, and the
records sit beside Railway's without touching them.

- **Receiving, such as `support@`:** Cloudflare Email Routing, which is free. It
  forwards an address to an existing inbox and adds its own MX and SPF records.
  Replying from `support@` needs a sending service (below) set up in Gmail as
  "Send mail as". A real mailbox, Google Workspace or Fastmail, replaces Email Routing
  if support grows.
- **Sending from the app,** such as the verification and reset codes in Phase 2 › 4:
  a transactional provider, chosen then. It sends from a subdomain, such as
  `mail.personagora.com`, so the app's sending reputation stays apart from replies
  people write. The provider gives SPF and DKIM records to add.
- **DMARC** is added with the first sender: a `_dmarc` TXT record at `p=none` to
  start, with reports, tightened to `quarantine` once the reports show only our
  senders.
- **Until then, nothing sends as the domain,** so a `v=spf1 -all` SPF record and a
  `p=reject` DMARC record stop anyone else from sending as it. Both change when the
  first sender or Email Routing is added.

## Steps for staging

1. **Code** (one PR): the `STAGING` value, both Dockerfiles, and the Caddyfile.
2. **Cloudflare:** move the nameservers (Tyler).
3. **Google:** the project, consent screen and staging client (Tyler).
4. **Railway:** the project, the `staging` environment, the four services, the
   custom domains (`railway domain`), and the repo connection. `.railway/railway.ts`
   was then pulled from it and holds the rest.
5. **Secrets:** the three secrets on `api`, in the dashboard (Tyler).
6. **DNS:** the records Railway shows for `staging.` and `api-staging.`.
7. **Check:** `/health` on `api-staging.` shows your own IP, sign in on `staging.`,
   and `plan.md` › 12 and 13's checks. Testing deployed environments beyond that is
   `plan.md` › Phase 2 › 6.

### Production

1. Create the `production` branch from `main`.
2. `railway config apply --environment production` creates the four services. Check
   the plan creates one volume per database: the file declares the volumes `config
   pull` imported, and the database helpers may make their own.
3. Its own OAuth client, and the three secrets on `api` (Tyler).
4. `railway domain personagora.com --service web --port 8080` and
   `railway domain api.personagora.com --service api --port 8000`, the records they
   show in Cloudflare, then `areDomainsRegistered: true` for production in the file.

`www.personagora.com` redirects to the bare domain at Cloudflare's edge and never
reaches Railway:

- **DNS:** an `AAAA` record for `www` pointing at `100::`, **proxied** (orange cloud).
  The address is a placeholder; a proxied record only needs to exist for the redirect
  rule to catch its traffic.
- **Rules → Redirect Rules:** Cloudflare's "Redirect from WWW to root" template, a 301
  to `https://personagora.com` with the path and query string kept.
