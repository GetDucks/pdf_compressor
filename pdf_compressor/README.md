# Target PDF Compressor

Static GitHub Pages frontend plus a Dockerized FastAPI/Ghostscript backend.

## Local startup

```bash
docker compose up --build
```

Open `http://localhost:8080`.

## GitHub Pages

1. Push the project to a GitHub repository on the `main` branch.
2. In **Settings → Pages**, choose **GitHub Actions**.
3. The Pages workflow deploys the `frontend` directory.

## Backend

The backend workflow publishes:

```text
ghcr.io/OWNER/REPOSITORY/backend:latest
```

Deploy that image on any Docker-capable host. Configure:

```text
PORT=8000
MAX_UPLOAD_BYTES=100000000
ALLOWED_ORIGINS=https://YOUR-GITHUB-PAGES-URL
```

Then change `frontend/config.js` from `http://localhost:8000` to the public backend URL and push again.

## Behavior

The API tests different image resolutions and returns the highest-quality result below the target. When the target cannot be reached above the chosen DPI floor, it returns the smallest acceptable result and reports that the target was not reached.

## Production notes

For public use, add rate limiting, malware scanning, usage quotas, a privacy policy, and a queued job system for large files.
