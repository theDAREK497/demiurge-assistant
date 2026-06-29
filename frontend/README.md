# Worldbuilder React/Vite Shell

This is the future React UI shell. The production-ready manual testing surface
is still the FastAPI-served vanilla UI at:

```text
http://127.0.0.1:8000/app/
```

Use this shell when we are ready to migrate the current UI module by module.

## Start

Install Node dependencies once:

```powershell
cd frontend
npm install
```

Run FastAPI in another terminal:

```powershell
.\.venv\Scripts\python.exe -m uvicorn worldbuilder_core.main:app --host 127.0.0.1 --port 8000
```

Run Vite:

```powershell
npm run dev
```

Open:

```text
http://127.0.0.1:5173/
```

The Vite dev server proxies `/api` and `/assets` to FastAPI.
