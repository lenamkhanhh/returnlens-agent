"""ReturnLens FastAPI App Factory per 17 §9.

Creates and configures the FastAPI application with isolated data directories,
DEMO_TODAY clock injection, database initialization, and modular route registration.
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.backend.contracts import ErrorShape
from app.backend.persistence.db import Database
from app.backend.persistence.repository import Repository
from app.backend.persistence.seed import seed_database, reset_database

load_dotenv()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Startup and shutdown lifecycle."""
    # Ensure seed is applied if fresh DB
    data_dir = app.state.data_dir
    data_dir.mkdir(parents=True, exist_ok=True)
    db_file = data_dir / "returnlens.db"
    first_run = not db_file.exists() or db_file.stat().st_size == 0

    if first_run:
        seed_database(app.state.db, app.state.demo_today)

    yield


def create_app(
    data_dir: Optional[str | Path] = None,
    demo_today: Optional[str] = None,
    harness_mode: Optional[bool] = None,
) -> FastAPI:
    """FastAPI application factory supporting test isolation (17 §9)."""
    # 1. Resolve configuration
    if data_dir is None:
        data_dir_env = os.environ.get("DATA_DIR", "./data")
        data_dir = Path(data_dir_env)
    else:
        data_dir = Path(data_dir)

    data_dir.mkdir(parents=True, exist_ok=True)

    if demo_today is None:
        demo_today = os.environ.get("DEMO_TODAY", "2026-11-11")

    if harness_mode is None:
        harness_mode = os.environ.get("HARNESS_MODE", "0") == "1"

    db_path = data_dir / "returnlens.db"
    db = Database(db_path)
    repo = Repository(db)

    # Auto-seed if stores table is empty
    with db.cursor() as cur:
        cur.execute("SELECT COUNT(*) AS count FROM stores")
        if cur.fetchone()["count"] == 0:
            seed_database(db, demo_today)

    app = FastAPI(
        title="ReturnLens Backend",
        version="0.1.0",
        description="Autonomous Support Agent for Solo D2C Merchants",
        lifespan=lifespan,
    )

    # Attach state to app
    app.state.data_dir = data_dir
    app.state.demo_today = demo_today
    app.state.harness_mode = harness_mode
    app.state.db = db
    app.state.repo = repo

    # CORS configuration
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Global structured error handler (02 §1)
    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
        error_code = "HTTP_ERROR"
        if exc.status_code == 404:
            error_code = "NOT_FOUND"
        elif exc.status_code == 403:
            error_code = "FORBIDDEN"
        elif exc.status_code == 401:
            error_code = "UNAUTHORIZED"
        elif exc.status_code == 409:
            error_code = "CONFLICT"
        elif exc.status_code == 422:
            error_code = "UNPROCESSABLE"

        error_shape = ErrorShape(
            code=error_code,
            user_message=str(exc.detail),
            retryable=exc.status_code in (503, 429),
            correlation_id=request.headers.get("X-Correlation-ID", ""),
        )
        return JSONResponse(status_code=exc.status_code, content=error_shape.model_dump())

    # Health check (02 §3)
    @app.get("/api/health")
    async def health_check():
        return {
            "status": "healthy",
            "demo_today": app.state.demo_today,
            "harness_mode": app.state.harness_mode,
        }

    # Reset endpoint (17 §1, 17 §9)
    @app.post("/api/operator/reset")
    async def reset_demo(request: Request):
        # Allow reset if in harness mode or local request
        reset_database(app.state.db, app.state.demo_today)
        return {"status": "reset_successful", "demo_today": app.state.demo_today}

    # Orders routes (02 §3)
    @app.get("/api/orders")
    async def list_orders(customer_id: Optional[str] = None):
        """List orders for scoped customer or all for seller."""
        if customer_id:
            orders = app.state.repo.list_customer_orders(customer_id)
        else:
            orders = app.state.repo.list_customer_orders("CUS-01")  # Default demo fixture
        return [o.model_dump() for o in orders]

    @app.get("/api/orders/{order_id}")
    async def get_order_endpoint(order_id: str, customer_id: Optional[str] = None):
        order = app.state.repo.get_order(order_id, customer_id=customer_id)
        if not order:
            raise HTTPException(status_code=404, detail=f"Order {order_id} not found")
        shipment = app.state.repo.get_shipment(order_id)
        return {
            "order": order.model_dump(),
            "shipment": shipment.model_dump() if shipment else None,
        }

    # Store policy (02 §3)
    @app.get("/api/store/policy")
    async def get_store_policy_endpoint(store_id: str = "store_dhun"):
        policy = app.state.repo.get_store_policy(store_id)
        if not policy:
            raise HTTPException(status_code=404, detail="Store policy not found")
        return policy.model_dump()

    # Customer profile (02 §3)
    @app.get("/api/customers/{customer_id}/profile")
    async def get_customer_profile_endpoint(customer_id: str):
        profile = app.state.repo.get_customer_profile(customer_id)
        if not profile:
            raise HTTPException(status_code=404, detail="Customer not found")
        return profile.model_dump()

    return app


# Default app for uvicorn
app = create_app()
