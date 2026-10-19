# FlowState website

The static site at https://runflowstate.vercel.app/ — plain HTML, CSS and
JS, no build step.

- `index.html`: the page. Download buttons link to
  `releases/latest/download/FlowStateSetup.exe` (Windows) and
  `releases/latest/download/FlowState-macOS.dmg` (Mac), so they always
  point at the newest release as long as both files are attached to it.
- `scripts/site.js`: demo animations, and platform detection that puts
  the visitor's own download button first and shows their shortcuts.
- `styles/site.css`, `assets/`: styles, fonts and images.

Deploy from this folder with the Vercel CLI (linked to the existing
project once):

```bash
npx vercel link
npx vercel deploy --prod
```
