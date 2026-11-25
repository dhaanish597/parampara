"""Tests for royalty splits, lineage, rounding, watermarks, and payouts (BUILD_PLAN 23)."""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from parampara.domain.generated import Provider, Role1, Scope3, Status1
from parampara.tools.payouts import create_payout
from parampara.tools.royalty import (
    build_fixed_licence_terms,
    generate_watermark_id,
    split_royalties,
)

PLATFORM = UUID("10000000-0000-4000-8000-000000000001")
FACTORY = UUID("10000000-0000-4000-8000-000000000002")
MASTER = UUID("20000000-0000-4000-8000-000000000001")
PARENT_MASTER = UUID("20000000-0000-4000-8000-000000000009")
REVIEWER = UUID("20000000-0000-4000-8000-000000000002")
TRAINEE_A = UUID("20000000-0000-4000-8000-000000000003")
TRAINEE_B = UUID("20000000-0000-4000-8000-000000000004")


def test_build_plan_23_2_exact_case_without_and_with_lineage() -> None:
    shares = split_royalties(
        price_paise=1_000_000,
        platform_org_id=PLATFORM,
        factory_org_id=FACTORY,
        master_user_id=MASTER,
        reviewer_user_id=REVIEWER,
        trainee_episodes={TRAINEE_A: 3, TRAINEE_B: 1},
    )
    by_id = {s.beneficiary_user_id or s.beneficiary_org_id: s.amount_paise for s in shares}
    assert by_id[PLATFORM] == 250_000
    assert by_id[FACTORY] == 100_000
    assert by_id[MASTER] == 325_000
    assert by_id[TRAINEE_A] == 195_000
    assert by_id[TRAINEE_B] == 65_000
    assert by_id[REVIEWER] == 65_000
    assert sum(s.amount_paise for s in shares) == 1_000_000

    with_lineage = split_royalties(
        price_paise=1_000_000,
        platform_org_id=PLATFORM,
        factory_org_id=FACTORY,
        master_user_id=MASTER,
        reviewer_user_id=REVIEWER,
        trainee_episodes={TRAINEE_A: 3, TRAINEE_B: 1},
        parent_master_user_id=PARENT_MASTER,
    )
    by_role = {
        s.role: s.amount_paise
        for s in with_lineage
        if s.role in (Role1.parent_master, Role1.master)
    }
    assert by_role[Role1.parent_master] == 81_250
    assert by_role[Role1.master] == 243_750
    assert sum(s.amount_paise for s in with_lineage) == 1_000_000


@pytest.mark.parametrize("price", [1, 7, 13, 99, 101, 999, 12_345, 987_654_321])
def test_royalty_property_sum_always_equals_price(price: int) -> None:
    shares = split_royalties(
        price_paise=price,
        platform_org_id=PLATFORM,
        factory_org_id=FACTORY,
        master_user_id=MASTER,
        reviewer_user_id=REVIEWER,
        trainee_episodes={TRAINEE_A: 5, TRAINEE_B: 2},
        parent_master_user_id=PARENT_MASTER,
    )
    assert sum(s.amount_paise for s in shares) == price
    assert all(s.amount_paise >= 0 for s in shares)


def test_watermark_terms_and_simulated_payout() -> None:
    wm = generate_watermark_id()
    assert wm.startswith("lic_") and len(wm) == 16
    terms = build_fixed_licence_terms(Scope3.robotics_research)
    assert terms.no_individual_productivity_scoring is True
    assert terms.no_biometric_identification is True
    assert terms.term_months == 12

    payout = create_payout(
        royalty_event_id=uuid4(),
        beneficiary_vpa="ramesh@upi",
        amount_paise=325_000,
        provider="simulated",
    )
    assert payout.provider == Provider.simulated
    assert payout.provider_ref.startswith("SIM-")
    assert payout.status == Status1.processed
