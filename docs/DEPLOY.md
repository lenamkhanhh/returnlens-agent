# ReturnLens Production Deployment Guide (Render)

This guide documents the exact configuration required to deploy the ReturnLens production demo on [Render](https://render.com).

> **Hackathon Notice**: In accordance with rule constraints, no third-party accounts or services are created automatically. This document provides the exact verified build and runtime settings for deployment.

---

## 1. Quick Deploy via Render Blueprint (Recommended)

ReturnLens includes a pre-configured [`render.yaml`](../render.yaml) file at the repository root.

1. Connect your GitHub repository to Render.
2. In the Render Dashboard, select **New** > **Blueprint**.
3. Select the `returnlens-agent` repository.
4. Render will detect `render.yaml` and prompt you to input the secret environment variables:
   - `GEMINI_API_KEY`
   - `SELLER_DEMO_PASSWORD`
   - `OPERATOR_PASSWORD`
5. Click **Apply**. Render will automatically build the frontend, install dependencies, and launch the service.

---

## 2. Manual Web Service Configuration

If creating the web service manually in the Render Dashboard, use the following exact settings:

### Service Details
| Setting | Value | Notes |
|---|---|---|
| **Service Type** | **Web Service** | Single service hosting FastAPI + Vite React SPA |
| **Name** | `returnlens-demo` | Public URL will be `https://returnlens-demo.onrender.com` |
| **Region** | `Singapore (Southeast Asia)` or `Oregon (US West)` | Low latency to target users |
| **Branch** | `main` | Production branch |
| **Runtime** | `Python` | Standard Python runtime with Node.js support |
| **Instance Type** | **Starter** ($7/mo) | *Recommended during hackathon judging to avoid ~50s free-tier spin-up latency. Free tier is supported.* |

### Build & Start Commands
| Setting | Exact Command |
|---|---|
| **Build Command** | `npm --prefix app/web install && npm --prefix app/web run build && pip install .` |
| **Start Command** | `uvicorn app.backend.main:app --host 0.0.0.0 --port $PORT` |

### Environment Variables
Configure the following environment variables under the **Environment** tab:

| Variable Name | Value | Type | Description |
|---|---|---|---|
| `PYTHON_VERSION` | `3.12.0` | Plain text | Enforces Python 3.12 runtime |
| `NODE_VERSION` | `20.10.0` | Plain text | Enforces Node 20 for Vite frontend build |
| `GEMINI_API_KEY` | *(your Gemini API key)* | **Secret** | Required for vision observation and transcription |
| `MODEL_PRIMARY` | `gemini-3.5-flash-lite` | Plain text | Unified primary model for evaluation & demo |
| `MODEL_FALLBACK` | `gemini-3.6-flash` | Plain text | Automatic fallback if daily quota is reached |
| `DEMO_SNAPSHOT` | `app/demo/snapshot/demo_cold_open.db` | Plain text | Pre-seeded database for instant cold-open state |
| `DEMO_TODAY` | `2026-11-11` | Plain text | Pinned demo simulation date |
| `HARNESS_MODE` | `0` | Plain text | Enforces IP rate limiting and password gates |
| `SELLER_DEMO_PASSWORD`| *(choose a secure password)* | **Secret** | Required for seller actions outside localhost |
| `OPERATOR_PASSWORD` | *(choose a secure password)* | **Secret** | Required for `/api/operator/reset` outside localhost |
| `DATA_DIR` | `./data` | Plain text | Local SQLite database storage path |

---

## 3. Alternative: Docker Container Deployment

A multi-stage [`Dockerfile`](../Dockerfile) is provided at the repository root.

To deploy via Docker on Render:
1. In Render Dashboard, choose **Environment: Docker**.
2. Specify Docker context: `.`
3. Set **DockerfilePath**: `./Dockerfile`.
4. Supply the environment variables listed in Section 2 above.

To build and run locally with Docker:
```bash
docker build -t returnlens:latest .
docker run -p 8000:8000 --env-file .env returnlens:latest
```

---

## 4. Production Safety & Defense Features

The production image incorporates defense-in-depth safeguards (Cards B15 & B16):

1. **Cold-Open State on Boot**:
   - The service automatically boots with `demo_cold_open.db` containing customer CUS-03 with orders ORD-1042 and ORD-4401 in `WAITING_RETURN`.
   - Judges can inspect active cases and approve/reject actions immediately without manual setup.
2. **Operator Demo Reset (`POST /api/operator/reset`)**:
   - Restores the clean cold-open state in `< 100ms`.
   - Protected by `OPERATOR_PASSWORD` when called from outside localhost (`X-Operator-Password` header).
3. **Public Rate Limiter**:
   - Restricts external IP addresses to **15 model calls per hour**.
   - Prevents abuse or quota drain on public hackathon demo links.
4. **Daily Budget Stop**:
   - Caps daily estimated model spend at **$3.00**.
   - If reached, new multimodal model invocations are gracefully paused, while deterministic WISMO queries remain fully functional.

---

## 5. Post-Deployment Verification Checklist

After deploying to Render, verify the service by executing these smoke tests:

1. **Frontend Root**:
   - Visit `https://<your-service>.onrender.com/` in an incognito browser.
   - Confirm the Vite React dashboard loads with customer and seller views.
2. **Health Check**:
   - `GET https://<your-service>.onrender.com/api/health`
   - Expected response: `{"status":"healthy","demo_today":"2026-11-11","harness_mode":false}`.
3. **Cold-Open Invariants**:
   - Open Seller View. Confirm 2 active cases are visible (`ORD-1042` and `ORD-4401`).
4. **WISMO Fast Path**:
   - In Customer View, query: *"Where is my order ORD-2030?"*
   - Expected response: Instant resolution with tracking status without consuming model budget.
5. **Reset Invariant**:
   - Send `POST https://<your-service>.onrender.com/api/operator/reset` with header `X-Operator-Password: <OPERATOR_PASSWORD>`.
   - Confirm status returns `{"status":"reset_successful", ...}` and active state is restored.
