# Step 2 — Design System, Base Layout & Homepage

## Session Goal
Implement the real visual design system in `tailwind.config.js`, build the shared layout (nav + footer + flash messages), and build the actual homepage with two feature cards linking to `/compress-pdf` and `/split-pdf`. Add custom 404/500 error pages that match the design.

## Context for the Agent
The project already has a working Flask + Tailwind pipeline from Step 1: app factory, `main` blueprint, `base.html`/`index.html` placeholders. **Inspect the existing `app/` folder before making changes** — do not recreate the venv or npm setup, they already exist. This step edits/extends existing files rather than starting fresh.

## Design Tokens — add to `tailwind.config.js` → `theme.extend.colors`

```js
colors: {
  ink: {
    50:  '#F4F6FA',
    100: '#E4E9F2',
    200: '#C7D1E3',
    300: '#9DADC9',
    400: '#6D80A8',
    500: '#4D5F8A',
    600: '#3A496D',
    700: '#2E3A57',
    800: '#212A3F',
    900: '#101B33',
    950: '#0A1122',
  },
  accent: {
    50:  '#EEFBF9',
    100: '#D3F4EE',
    200: '#A6E8DD',
    300: '#6FD6C6',
    400: '#3DBBA9',
    500: '#0FA294',
    600: '#0D9488',
    700: '#0A6259',
    800: '#0A4E47',
    900: '#08403B',
  },
}
```

Other conventions: `rounded-xl` for cards, `rounded-lg` for buttons/inputs, `shadow-sm` default / `shadow-md` on hover for cards, system font stack (Tailwind's default `font-sans`, no external font import).

## Tasks

1. Update `tailwind.config.js` with the color tokens above.

2. **`app/templates/partials/nav.html`**: sticky top nav, `bg-ink-900 text-white`. Site name "PDF Toolkit" on the left. Two links on the right: "Compress PDF" → `/compress-pdf`, "Split PDF" → `/split-pdf`. Active link gets an `accent-400` underline/highlight, determined in Jinja by comparing `request.path`. On small screens, links collapse behind a hamburger button toggled by vanilla JS (see task 8).

3. **`app/templates/partials/footer.html`**: small, muted (`text-gray-500 text-sm`), one line: "Media Pons PDF Tools".

4. **`app/templates/partials/flash.html`**: reusable component that loops Flask's `get_flashed_messages(with_categories=true)` and renders each with category-based styling (e.g. `success` → green left border + light green bg, `error` → red, `warning` → amber, `info` → ink/accent). Included in `base.html` just above `{% block content %}`.

5. **Rewrite `app/templates/base.html`**: proper `<head>` (viewport meta, `{% block title %}`, link to compiled CSS, favicon if you add one), include `partials/nav.html`, include `partials/flash.html`, `{% block content %}{% endblock %}`, include `partials/footer.html`, `<script src="/static/js/common.js">` before `</body>`.

6. **Rewrite `app/templates/index.html`**: short hero (one heading + one-sentence subtitle about the toolkit), then a responsive grid (`grid-cols-1 md:grid-cols-2 gap-6`) of two feature cards:
   - **Compress PDF**: simple inline SVG icon (hand-drawn line icon, no external icon library needed for just two icons), title, description — *"Reduce your PDF's file size while keeping it readable — perfect for email attachments and faster uploads."* — whole card wrapped in `<a href="/compress-pdf">`.
   - **Split PDF**: inline SVG icon, title, description — *"Pull an exact page range out of your PDF into a brand-new file — no need to touch the original."* — wrapped in `<a href="/split-pdf">`.
   - Card style: `bg-white border border-ink-100 rounded-xl p-6 hover:shadow-md hover:border-accent-300 transition`.

7. **Error pages**: `app/templates/errors/404.html` and `errors/500.html`, extending `base.html`, friendly copy ("Page not found" / "Something went wrong"), a link back to `/`. Register both with `@app.errorhandler(404)` / `@app.errorhandler(500)` in `app/__init__.py`, rendering these templates with the correct status code.

8. **`app/static/js/common.js`**: mobile nav toggle (show/hide the collapsed link list on hamburger click), plus a small helper that auto-dismisses flash messages after ~5 seconds by fading them out. Keep this file small and focused.

9. **Placeholder routes**: add `/compress-pdf` and `/split-pdf` routes to the `main` blueprint for now, each rendering a simple "Under Development" page using the full base layout (so the nav and cards are fully clickable and the app feels navigable end-to-end at every stage of development). These placeholder routes/templates will be **entirely replaced** in Steps 3 and 4 by their own dedicated blueprints.

## Definition of Done
- [ ] Homepage shows two styled cards with icons, titles, and descriptions using the ink/accent palette
- [ ] Nav bar appears on every page; links work; the current page's link is visibly highlighted; the mobile menu opens/closes correctly on a narrow viewport
- [ ] Visiting a nonexistent URL shows the custom 404 page in the app's visual style, not Flask's default error page
- [ ] Triggering a flash message (temporarily, for testing) renders correctly and auto-dismisses
- [ ] The whole site is usable at a mobile width (~375px): nav collapses, cards stack to one column

## Out of Scope for This Step
- Do not implement any file upload, compression, or splitting logic.
- Do not add real backend logic beyond the "coming soon" placeholders for `/compress-pdf` and `/split-pdf`.
