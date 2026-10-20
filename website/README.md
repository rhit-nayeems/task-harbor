# Task Harbor website

Static HTML, CSS, and JavaScript. No runtime dependencies or build framework.
The example review output is illustrative, not a connection to an agent.

## Preview

From the repository root:

```sh
python -m http.server 8765 --directory website
```

Open http://localhost:8765. Installation copy buttons need a secure browser
context (localhost or HTTPS); a selection fallback is provided.

## Build

```sh
node website/build.mjs
```

Publish `website/dist/` on any static host.
Google Fonts supplies Archivo, Inter Tight, JetBrains Mono, and Newsreader,
with local font fallbacks.
There are no analytics, cookies, account forms, or provider calls.

## Deploy to Cloudflare

Live site: https://task-harbor.sk-naimulnayeem.workers.dev

The site uses Workers Static Assets. Only the four built files in `dist/`
are published; no Worker code or paid services are required.

With Node.js 22.18 or newer:

```sh
cd website
npm ci
npx cf auth login
npm run deploy
```

Check the signed-in account with `npx cf auth whoami` before deploying.
`cloudflare.config.ts` defines the site name; the CLI-generated
`wrangler.config.ts` points its build tool at `dist/`.
Credentials stay in the CLI's local account configuration.

Changes under `website/` pushed to `main` deploy automatically through
[GitHub Actions](https://github.com/rhit-nayeems/task-harbor/actions/workflows/website.yml).
Pull requests check the build without deploying. The workflow also supports
manual runs from the Actions page. Every deployment checks that the live files
match the build.

The workflow uses the repository secrets `CLOUDFLARE_API_TOKEN` and
`CLOUDFLARE_ACCOUNT_ID`. The deployment token has Workers Scripts Write and
Account Settings Read permissions for the hosting account.

## Check changes

Run `node --check website/app.js`, then check desktop and narrow mobile layouts.
Check clipboard copying, its fallback, keyboard focus, contribution links,
and internal navigation. Confirm
that example content and product claims still match the CLI.
