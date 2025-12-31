Binsmith Web UI
===============

The web UI is a React app that talks to the Binsmith server over the AG-UI API.
It shares sessions/threads with the TUI, so you can switch between clients.

---

## Requirements

- Node 18+
- Binsmith server running locally or remotely

---

## Install & Run

```bash
cd frontend
npm install
npm run dev
```

By default it targets `http://localhost:8000`.
To point at a different server, create `frontend/.env.local`:

```bash
VITE_BINSMITH_SERVER_URL=http://your-server:8000
```

---

## Usage Notes

- The sidebar includes a **Model** selector (lazy-loaded + searchable).
- The header shows the active model and streaming status.
- Threads and history are shared with the TUI.

---

## Troubleshooting

- **Model errors**: If a model's API key isn't set on the server, the UI will surface a clear error.
- **CORS**: If you host the UI separately, ensure the server is reachable and CORS is allowed.
