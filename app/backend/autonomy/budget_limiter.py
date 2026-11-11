"""Budget Limiter, IP Rate Limiter, and Access Gates (21 P3, 17 §9, B16).

Enforces:
1. Per-IP model rate limit (default 10 calls/IP/hour) to prevent public spam on live demo.
2. Daily estimated model budget stop (stops new model calls when daily cost reaches $3.00).
   Fast-path WISMO remains available.
3. Access gates for SELLER_DEMO_PASSWORD and OPERATOR_PASSWORD outside localhost.
"""

from __future__ import annotations

import os
import time
from collections import defaultdict
from typing import Dict, List, Optional
from fastapi import HTTPException, Request


class IPRateLimiter:
    """Sliding-window per-IP rate limiter (default: 10 requests / 3600 seconds)."""

    def __init__(self, limit: int = 10, window_seconds: int = 3600) -> None:
        self.limit = limit
        self.window_seconds = window_seconds
        self._history: Dict[str, List[float]] = defaultdict(list)

    def check_and_record(self, client_ip: str) -> bool:
        """Returns True if request is allowed, False if rate limit exceeded."""
        now = time.time()
        # Clean older entries
        cutoff = now - self.window_seconds
        self._history[client_ip] = [t for t in self._history[client_ip] if t > cutoff]
        if len(self._history[client_ip]) >= self.limit:
            return False
        self._history[client_ip].append(now)
        return True


class DailyBudgetTracker:
    """Tracks estimated daily model invocation costs ($3.00 stop per 21 P3)."""

    def __init__(self, daily_budget_usd: float = 3.00, est_cost_per_call: float = 0.002) -> None:
        self.daily_budget_usd = daily_budget_usd
        self.est_cost_per_call = est_cost_per_call
        self.current_day: str = ""
        self.daily_calls: int = 0

    def is_budget_exceeded(self, today_str: str) -> bool:
        if self.current_day != today_str:
            self.current_day = today_str
            self.daily_calls = 0
        return (self.daily_calls * self.est_cost_per_call) >= self.daily_budget_usd

    def record_call(self, today_str: str) -> None:
        if self.current_day != today_str:
            self.current_day = today_str
            self.daily_calls = 0
        self.daily_calls += 1


# Global singletons
ip_rate_limiter = IPRateLimiter(limit=15, window_seconds=3600)
budget_tracker = DailyBudgetTracker(daily_budget_usd=3.00)


def verify_operator_access(request: Request, harness_mode: bool = False) -> None:
    """Verify operator access outside localhost."""
    if harness_mode:
        return
    client_host = request.client.host if request.client else "127.0.0.1"
    if client_host in ("127.0.0.1", "::1", "localhost", "testclient"):
        return

    op_pass = os.environ.get("OPERATOR_PASSWORD")
    if not op_pass:
        # Operator endpoints disabled by default outside localhost if password unset
        raise HTTPException(status_code=403, detail="Operator access is disabled outside localhost")

    auth_hdr = (
        request.headers.get("X-Operator-Password")
        or request.headers.get("Authorization", "").replace("Bearer ", "")
    )
    if auth_hdr != op_pass:
        raise HTTPException(status_code=403, detail="Operator password required")


def verify_seller_access(request: Request, harness_mode: bool = False) -> None:
    """Verify seller access outside localhost if SELLER_DEMO_PASSWORD is set."""
    if harness_mode:
        return
    client_host = request.client.host if request.client else "127.0.0.1"
    if client_host in ("127.0.0.1", "::1", "localhost", "testclient"):
        return

    # The public demo UI has no password prompt, so the seller gate is opt-in
    # (SELLER_GATE=1). Money actions are mock; the per-IP rate limit still applies.
    if os.environ.get("SELLER_GATE") != "1":
        return
    seller_pass = os.environ.get("SELLER_DEMO_PASSWORD")
    if not seller_pass:
        return

    auth_hdr = (
        request.headers.get("X-Seller-Password")
        or request.headers.get("Authorization", "").replace("Bearer ", "")
    )
    if auth_hdr != seller_pass:
        raise HTTPException(status_code=401, detail="Seller password required")
