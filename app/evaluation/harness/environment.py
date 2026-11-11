"""Isolated trial environment runtime per 17 §9.

Provides isolated temporary DATA_DIR, database seeding, ASGI transport client,
fixed DEMO_TODAY clock, and worker restart capability for S09.
"""

from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path
from typing import Optional

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.backend.main import create_app
from app.backend.mock.tools import MockToolService
from app.backend.persistence.db import Database
from app.backend.persistence.repository import Repository
from app.backend.persistence.seed import seed_database
from app.backend.workflow.engine import WorkflowEngine


class TrialEnvironment:
    """Manages full isolation for a single test trial (17 §9)."""

    def __init__(
        self,
        demo_today: str = "2026-11-11",
        custom_data_dir: Optional[str | Path] = None,
    ) -> None:
        self.demo_today = demo_today
        self._temp_dir_obj: Optional[tempfile.TemporaryDirectory] = None

        if custom_data_dir:
            self.data_dir = Path(custom_data_dir)
            self.data_dir.mkdir(parents=True, exist_ok=True)
        else:
            self._temp_dir_obj = tempfile.TemporaryDirectory(prefix="returnlens_trial_")
            self.data_dir = Path(self._temp_dir_obj.name)

        self.db_path = self.data_dir / "returnlens.db"
        self.app: Optional[FastAPI] = None
        self.transport: Optional[ASGITransport] = None
        self.client: Optional[AsyncClient] = None
        self.db: Optional[Database] = None
        self.repo: Optional[Repository] = None

    async def __aenter__(self) -> "TrialEnvironment":
        await self.setup()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.teardown()

    async def setup(self) -> None:
        """Initialize isolated app, seeded database, and ASGI client."""
        # 1. Create FastAPI app with isolated data_dir
        os.environ["DATA_DIR"] = str(self.data_dir)
        os.environ["HARNESS_MODE"] = "1"


        self.app = create_app(
            data_dir=self.data_dir,
            demo_today=self.demo_today,
            harness_mode=True,
        )

        # 2. Reorder routes so any static mount at root does not capture /api
        mounts = [r for r in self.app.router.routes if type(r).__name__ == "Mount"]
        others = [r for r in self.app.router.routes if type(r).__name__ != "Mount"]
        self.app.router.routes = others + mounts

        # 3. Cache references from app state
        self.db = self.app.state.db
        self.repo = self.app.state.repo

        try:
            from app.backend.autonomy.router import get_repository
            self.app.dependency_overrides[get_repository] = lambda: self.repo
        except Exception:
            pass

        # 4. Initialize ASGI transport and client
        self.transport = ASGITransport(app=self.app)
        self.client = AsyncClient(transport=self.transport, base_url="http://test")

    async def teardown(self) -> None:
        """Clean up client, connections, and temporary directory."""
        if self.client:
            await self.client.aclose()
            self.client = None

        if self._temp_dir_obj:
            try:
                self._temp_dir_obj.cleanup()
            except Exception:
                pass
            self._temp_dir_obj = None

    def restart_worker(self) -> WorkflowEngine:
        """Simulate in-process worker restart for S09 per 17 §9.

        Destroys the current engine in app.state and re-instantiates it
        pointing to the existing database and storage on disk.
        """
        assert self.app is not None
        assert self.repo is not None

        # Re-create mock service and engine
        mock_service = MockToolService(self.repo)
        new_engine = WorkflowEngine(self.repo, mock_service)

        # Replace in app state
        self.app.state.mock_service = mock_service
        self.app.state.engine = new_engine
        return new_engine
