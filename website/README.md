# Task Harbor website

Static HTML, CSS, and JavaScript. No runtime dependencies or build framework.
The interactive terminal is an illustrative demo, not a connection to an agent.

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

Publish `website/dist/` on any static host. The Sites manifest stores the
registered private preview identity; credentials are never stored here.
Google Fonts supplies DM Sans and IBM Plex Mono, with local font fallbacks.
There are no analytics, cookies, account forms, or provider calls.

## Check changes

Run `node --check website/app.js`, then check desktop and narrow mobile layouts.
Exercise all four task stages, arrow-key navigation between tabs, both install
methods, clipboard copying, FAQ expansion, and internal navigation. Confirm
that example content and product claims still match the CLI.
