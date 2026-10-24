# Tally

A mobile-first, frontend-only personal finance demo built with React, TypeScript, Vite, Tailwind, and hand-drawn SVG charts. Receipt, shopping list, and recommendation data stays in the browser's local storage. No account or backend is needed.

## Run locally

```sh
npm install
npm run dev
```

Open the local URL Vite prints. The layout is designed for a 390 × 844 phone viewport and centers in a 430px column on desktop. Use the small settings control at the top right to reset demo data.

## What’s included

- Home, Dashboard, Scan, Receipt Detail, Shopping List, Compare, Predict, Rewind, and Group screens
- Mock receipt history, local edits, and persisted shopping list
- Camera permission flow with upload fallback; scanning uses a mock receipt
- Responsive five-slot bottom navigation and accessible focus/tap states
