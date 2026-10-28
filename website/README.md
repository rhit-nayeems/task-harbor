# Task Harbor website

React, TypeScript, Vite, and Tailwind. Source is in `../design-lab/src/`.
Workflow examples are illustrative and do not make provider calls.

## Preview

```sh
cd design-lab
npm ci
npm run dev
```

Open http://127.0.0.1:8772/.

## Production build

From the repository root:

```sh
npm ci --prefix design-lab
npm ci --prefix website
npm run build --prefix website
```

The build checks TypeScript, bundles the site, and replaces `website/dist/`.
Publish that directory on a static host. The site has no analytics, account
forms, or provider calls. Google Fonts supplies Archivo and JetBrains Mono.

## Deployment

Changes to `design-lab/`, `website/`, or the website workflow pushed to `main`
deploy to https://task-harbor.sk-naimulnayeem.workers.dev/ through GitHub Actions.
Pull requests build and run a deployment dry run without publishing.
The workflow compares every deployed asset with its build output.

The existing Cloudflare configuration and repository deployment secrets are
used. With an authenticated Cloudflare CLI, `npm run deploy --prefix website`
can also deploy manually.
