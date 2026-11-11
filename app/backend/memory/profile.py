"""Customer Profile and Cross-Session Memory Management.

Card B13: Manages CustomerProfile persistence across chat sessions per 02 §2 and 17 §2:
- Tracks preferred_language, refund_destination (UPI/store_credit/original), open_case_ids, prior_case_count.
- Provides trusted context for the resolution planner.
- Test 48: Ensures returning customers are remembered across sessions/restarts.
- Does NOT store chain-of-thought or use memory for fraud scoring (02 §2, 15 B13).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import List, Optional

from app.backend.contracts import CustomerProfile, Language
from app.backend.persistence.repository import Repository


def get_or_create_customer_profile(
    repo: Repository,
    customer_id: str,
    store_id: str = "store_dhun",
) -> CustomerProfile:
    """Retrieve existing customer profile from DB, or create default."""
    profile = repo.get_customer_profile(customer_id)
    if profile:
        return profile

    now_iso = datetime.now(timezone.utc).isoformat()
    # Create default customer record in DB
    with repo.db.transaction() as conn:
        conn.execute(
            """
            INSERT OR IGNORE INTO customers (
                customer_id, store_id, name, phone, preferred_language,
                refund_destination, prior_case_count, updated_at
            ) VALUES (?, ?, ?, '', 'en', 'original', 0, ?)
            """,
            (customer_id, store_id, f"Customer {customer_id}", now_iso),
        )

    return repo.get_customer_profile(customer_id) or CustomerProfile(
        customer_id=customer_id,
        store_id=store_id,
        name=f"Customer {customer_id}",
        preferred_language=Language.EN,
        refund_destination="original",
        updated_at=now_iso,
    )


def update_customer_memory(
    repo: Repository,
    customer_id: str,
    preferred_language: Optional[Language] = None,
    refund_destination: Optional[str] = None,
    case_id: Optional[str] = None,
    increment_prior_case_count: bool = False,
) -> CustomerProfile:
    """Update customer memory attributes from conversation insights."""
    profile = get_or_create_customer_profile(repo, customer_id)
    now_iso = datetime.now(timezone.utc).isoformat()

    new_lang = preferred_language.value if preferred_language else profile.preferred_language.value
    new_dest = refund_destination if refund_destination else profile.refund_destination
    new_count = profile.prior_case_count + (1 if increment_prior_case_count else 0)

    with repo.db.transaction() as conn:
        conn.execute(
            """
            UPDATE customers SET
                preferred_language = ?,
                refund_destination = ?,
                prior_case_count = ?,
                updated_at = ?
            WHERE customer_id = ?
            """,
            (new_lang, new_dest, new_count, now_iso, customer_id),
        )

    return repo.get_customer_profile(customer_id) or profile


def format_memory_chips(profile: CustomerProfile) -> List[str]:
    """Format trusted memory context chips for planner and seller console (17 §2, 17 §5)."""
    chips: List[str] = [
        f"preferred_language={profile.preferred_language.value}",
        f"refund_destination={profile.refund_destination}",
    ]
    if profile.prior_case_count > 0:
        chips.append(f"prior_cases={profile.prior_case_count}")
    if profile.open_case_ids:
        chips.append(f"open_cases={len(profile.open_case_ids)}")
    return chips
