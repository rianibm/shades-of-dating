# Date Plan Jakarta

A small Indonesian-language date planner. The front end uses Vite (managed with
Yarn); a standard-library Python API ranks ten curated Jakarta ideas using the
area, budget, activity, and date-style answers. Personalization runs locally and
does not need an AI provider, API key, account, or saved answers.

## Run locally

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

## Validate

```sh
python3 -m unittest discover -s tests
yarn build
```

Prices are rough planning estimates, not live ticket data. Each idea links to a
map search and some link directly to the venue's public website. Check current
prices, hours, access, and availability before visiting.
