"""Test-mode UPI payout provider interface (BUILD_PLAN 23.3)."""

from __future__ import annotations

import secrets
from datetime import UTC, datetime
from typing import Literal
from uuid import UUID, uuid4

from parampara.domain.generated import Payout, Provider, Status1


def create_payout(
    *,
    royalty_event_id: UUID,
    beneficiary_vpa: str | None,
    amount_paise: int,
    provider: Literal["razorpayx_test", "simulated"] = "simulated",
) -> Payout:
    """Create a test-mode payout record. Real money never moves."""
    if amount_paise < 0:
        raise ValueError("amount_paise cannot be negative")
    now = datetime.now(UTC)
    if provider == "razorpayx_test" and beneficiary_vpa:
        ref = f"pout_test_{secrets.token_hex(6)}"
        return Payout(
            id=uuid4(),
            royalty_event_id=royalty_event_id,
            provider=Provider.razorpayx_test,
            provider_ref=ref,
            status=Status1.queued,
            created_at=now,
        )
    ref = f"SIM-{secrets.token_hex(4).upper()}"
    return Payout(
        id=uuid4(),
        royalty_event_id=royalty_event_id,
        provider=Provider.simulated,
        provider_ref=ref,
        status=Status1.processed,
        created_at=now,
    )
