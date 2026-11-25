"""Deterministic integer-paise royalty split and watermark helper (BUILD_PLAN 23.1-23.2)."""

from __future__ import annotations

import secrets
import string
from dataclasses import dataclass
from fractions import Fraction
from uuid import UUID

from parampara.domain.generated import LicenceTerms, Role1, Scope3

BASE32_ALPHABET = string.ascii_lowercase + "234567"
RawEntry = tuple[Role1, UUID | None, UUID | None, Fraction, dict[str, float | str]]


@dataclass(frozen=True)
class RoyaltyShare:
    role: Role1
    beneficiary_user_id: UUID | None
    beneficiary_org_id: UUID | None
    amount_paise: int
    basis: dict[str, float | str]


def generate_watermark_id() -> str:
    """Return 'lic_' + 12 random base32 characters (BUILD_PLAN 23.1)."""
    return "lic_" + "".join(secrets.choice(BASE32_ALPHABET) for _ in range(12))


def build_fixed_licence_terms(scope: Scope3) -> LicenceTerms:
    """Build immutable licence terms with mandatory no-surveillance & no-biometrics clauses."""
    return LicenceTerms(
        scope=scope,
        no_individual_productivity_scoring=True,
        no_biometric_identification=True,
        attribution_required=True,
        term_months=12,
    )


def _master_entries(
    pool: Fraction, master_id: UUID, parent_id: UUID | None, *, include_trainee_pool: bool = False
) -> list[RawEntry]:
    master_frac = pool * Fraction(90 if include_trainee_pool else 50, 100)
    if parent_id is not None and parent_id != master_id:
        p_frac = master_frac * Fraction(25, 100)
        m_frac = master_frac * Fraction(75, 100)
        return [
            (
                Role1.parent_master,
                parent_id,
                None,
                p_frac,
                {"share": float(p_frac), "lineage": "parent_25pct"},
            ),
            (
                Role1.master,
                master_id,
                None,
                m_frac,
                {"share": float(m_frac), "lineage": "child_75pct"},
            ),
        ]
    return [(Role1.master, master_id, None, master_frac, {"share": float(master_frac)})]


def _exact_fractions(
    platform_org_id: UUID,
    factory_org_id: UUID,
    master_user_id: UUID,
    reviewer_user_id: UUID,
    trainee_episodes: dict[UUID, int],
    parent_master_user_id: UUID | None,
) -> list[RawEntry]:
    if any(ep < 0 for ep in trainee_episodes.values()):
        raise ValueError("trainee_episodes counts must be non-negative")
    pool = Fraction(65, 100)
    total_ep = sum(trainee_episodes.values())
    entries: list[RawEntry] = [
        (Role1.platform, None, platform_org_id, Fraction(25, 100), {"share": 0.25}),
        (Role1.factory, None, factory_org_id, Fraction(10, 100), {"share": 0.10}),
        *_master_entries(
            pool, master_user_id, parent_master_user_id, include_trainee_pool=(total_ep == 0)
        ),
    ]
    if total_ep > 0:
        for tid, ep_count in sorted(trainee_episodes.items(), key=lambda kv: str(kv[0])):
            if ep_count == 0:
                continue
            t_frac = pool * Fraction(40, 100) * Fraction(ep_count, total_ep)
            basis: dict[str, float | str] = {
                "episodes": float(ep_count),
                "total_episodes": float(total_ep),
            }
            entries.append((Role1.trainee, tid, None, t_frac, basis))
    rev_frac = pool * Fraction(10, 100)
    entries.append((Role1.reviewer, reviewer_user_id, None, rev_frac, {"share": float(rev_frac)}))
    return entries


def split_royalties(
    *,
    price_paise: int,
    platform_org_id: UUID,
    factory_org_id: UUID,
    master_user_id: UUID,
    reviewer_user_id: UUID,
    trainee_episodes: dict[UUID, int],
    parent_master_user_id: UUID | None = None,
) -> list[RoyaltyShare]:
    """Compute exact integer-paise shares summing to price_paise (largest-remainder rounding)."""
    if price_paise <= 0:
        raise ValueError("price_paise must be positive")
    raw = _exact_fractions(
        platform_org_id,
        factory_org_id,
        master_user_id,
        reviewer_user_id,
        trainee_episodes,
        parent_master_user_id,
    )
    floors = [int(frac * price_paise) for _, _, _, frac, _ in raw]
    rem = sorted(
        (
            (frac * price_paise - floors[i], str(u or o or ""), i)
            for i, (_, u, o, frac, _) in enumerate(raw)
        ),
        key=lambda item: (-item[0], item[1]),
    )
    for i in range(price_paise - sum(floors)):
        floors[rem[i][2]] += 1
    return [RoyaltyShare(r, u, o, floors[i], b) for i, (r, u, o, _, b) in enumerate(raw)]
