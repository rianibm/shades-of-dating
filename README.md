# Date Plan Jakarta

A small Indonesian-language date planner. The front end uses Vite (managed with
Yarn); a standard-library Python API ranks ten curated Jakarta ideas using the
area, budget, activity, and date-style answers. Personalization runs locally and
does not need an AI provider, API key, account, or saved answers.

## Run locally

### Option A — Vite + Python API

Use two terminals from the project root:

```sh
python3 app.py
```

```sh
yarn install
yarn dev
```

Open the local URL printed by Vite. Its development server proxies `/api` calls
to the Python server at `127.0.0.1:8000`.

### Option B — Netlify dev (production-like)

```sh
yarn install
netlify dev
```

This serves the Vite build pipeline and Netlify Functions on the same origin,
matching production routing for `/api/*`.

## Deploy on Netlify

The site builds with Vite and serves API routes from Netlify Functions.

1. Connect the repo in Netlify (build settings come from `netlify.toml`).
2. Add environment variables in the Netlify UI:
   - `AI_GATEWAY_API_KEY` — required for AI date plans (from [Vercel AI Gateway](https://vercel.com/ai-gateway)).
   - `AI_GATEWAY_MODEL` — optional; defaults to `openai/gpt-4.1-mini`.
3. Deploy. `/api/recommendations` and `/api/health` are rewritten to functions.

Curated venue data lives in `data/curated-data.json` and is shared by the Python
API and Netlify Functions.

## Validate

```sh
python3 -m unittest discover -s tests
yarn build
```

Prices are rough planning estimates, not live ticket data. Each idea links to a
map search and some link directly to the venue's public website. Check current
prices, hours, access, and availability before visiting.
