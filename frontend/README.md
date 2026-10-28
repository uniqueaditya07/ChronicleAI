# ChronicleAI frontend

React 19 and Vite 8 provide case management, evidence upload/search, entities, Gemini analysis/chat, an evidence-linked timeline, report download, and the paginated Evidence Inspector.

See the [root README](../README.md) for backend configuration, complete setup, isolated backend testing, and the presentation walkthrough.

## Run locally

Start FastAPI on `127.0.0.1:8000`, then run from this directory:

```powershell
npm ci
npm run dev -- --host 127.0.0.1 --port 5173 --strictPort
```

Open `http://127.0.0.1:5173`. The `/api` proxy in `vite.config.js` targets port 8000. Gemini credentials belong only in the backend environment, never frontend configuration.

## Checks

```powershell
npm test
npm run lint
npm run build
```

The 128 Node tests execute actual production handlers with simulated React hooks and controlled request ordering. They cover stale responses, loading/errors, Inspector pagination, chat/timeline isolation, and report download guards. They do not render React or replace browser verification.

Build output is generated in ignored `dist/`. Hosting those files alone does not supply the API; a production hosting configuration is outside this local project's scope.

## Behavior to preserve

- Superseded requests are aborted where practical and also checked by request identity.
- Inspector pages contain at most 2,000 lines; citations request their target page, file, and line.
- Chat belongs to the current case view and clears on navigation/new evidence.
- Reports download as HTML, with printing/Save as PDF in a normal browser.
- Timestamps display in browser local time, with UTC database values interpreted consistently.
