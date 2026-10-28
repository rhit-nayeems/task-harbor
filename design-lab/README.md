# Task Harbor website design

The complete new website is at http://127.0.0.1:8772/.
It presents Task Harbor as a small engineering team in your terminal, with agent
roles, an interactive task constellation, verification details, installation,
FAQs, and contribution links.

```sh
cd design-lab
npm ci
npm run dev
```

`npm run build` checks TypeScript and creates the static site in `dist/`.
The production build in `website/build.mjs` compiles this source and copies the
result to `website/dist/`. Changes here pushed to main deploy automatically.

The workflow uses illustrative tasks. No model calls are made. Stage buttons
stop automatic playback; replay runs the sequence again. The header's motion
control pauses page motion. Reduced motion disables automatic playback.

Earlier concepts remain at `/git-map#workflow`, `/terminal#workflow`, and
`/combined`. Add `?concepts` to the root URL to show the comparison controls.

Initial source recovered from Lovable project
`863154f5-c315-4990-9628-3b98a76143ae`, then repaired and extended locally.
Remote Lovable files have not been updated.
