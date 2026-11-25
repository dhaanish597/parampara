"""Tests for W3C VC eddsa-jcs-2022 tools: jcs, multikey, vc (BUILD_PLAN 20.1-20.2)."""

from __future__ import annotations

import base64
import copy
import json
from pathlib import Path
from typing import Any

from parampara.domain.generated import ProofOfSkillCredential
from parampara.tools.jcs import canonicalize_bytes
from parampara.tools.multikey import (
    build_did_document,
    decode_public_multikey,
    encode_public_multikey,
    keypair_from_seed_b64,
)
from parampara.tools.vc import sign_credential, verify_credential

ROOT = Path(__file__).resolve().parents[3]
CRED_FIXTURE = ROOT / "contracts" / "fixtures" / "credential.json"
VECTORS_PATH = ROOT / "contracts" / "fixtures" / "vectors" / "vc-vectors.json"

TEST_SEED_B64 = base64.b64encode(bytes(range(32))).decode("ascii")
OTHER_SEED_B64 = base64.b64encode(bytes(range(32, 64))).decode("ascii")


def _unsigned_cred() -> dict[str, Any]:
    raw: dict[str, Any] = json.loads(CRED_FIXTURE.read_text(encoding="utf-8"))
    raw.pop("proof", None)
    return raw


def test_jcs_canonicalize_sorts_keys_deterministically() -> None:
    assert canonicalize_bytes({"b": 1, "a": 2}) == b'{"a":2,"b":1}'


def test_multikey_roundtrip_and_did_doc() -> None:
    signing_key, pub_bytes = keypair_from_seed_b64(TEST_SEED_B64)
    assert signing_key is not None
    multibase = encode_public_multikey(pub_bytes)
    assert multibase.startswith("z6Mk")
    assert decode_public_multikey(multibase) == pub_bytes

    did_doc = build_did_document(
        issuer_did="did:web:parampara.app",
        key_id="key-1",
        public_key_bytes=pub_bytes,
    )
    assert did_doc["id"] == "did:web:parampara.app"
    assert did_doc["assertionMethod"] == ["did:web:parampara.app#key-1"]
    assert did_doc["verificationMethod"][0]["publicKeyMultibase"] == multibase


def test_sign_verify_and_tamper_detection() -> None:
    signing_key, pub_bytes = keypair_from_seed_b64(TEST_SEED_B64)
    _, other_pub = keypair_from_seed_b64(OTHER_SEED_B64)
    signed = sign_credential(
        unsigned_vc=_unsigned_cred(),
        signing_key=signing_key,
        verification_method="did:web:parampara.app#key-1",
        created="2026-11-26T00:00:00Z",
    )
    ProofOfSkillCredential.model_validate(signed)
    assert verify_credential(signed, pub_bytes) is True

    tampered = copy.deepcopy(signed)
    tampered["credentialSubject"]["performance"]["clean_runs"] += 1
    assert verify_credential(tampered, pub_bytes) is False
    assert verify_credential(signed, other_pub) is False


def test_shared_vc_vectors_match_expectations() -> None:
    vectors: list[dict[str, Any]] = json.loads(VECTORS_PATH.read_text(encoding="utf-8"))
    assert len(vectors) >= 3
    for vec in vectors:
        pub_bytes = decode_public_multikey(vec["publicKeyMultibase"])
        assert verify_credential(vec["vc"], pub_bytes) is vec["expected_valid"], vec["name"]


def test_verify_rejects_tampered_proof_metadata_even_if_resigned() -> None:
    signing_key, pub_bytes = keypair_from_seed_b64(TEST_SEED_B64)
    signed = sign_credential(
        unsigned_vc=_unsigned_cred(),
        signing_key=signing_key,
        verification_method="did:web:parampara.app#key-1",
        created="2026-11-26T00:00:00Z",
    )
    for field, bad_val in (
        ("cryptosuite", "eddsa-rdfc-2022"),
        ("type", "OtherProof"),
        ("proofPurpose", "authentication"),
        ("verificationMethod", "did:web:other.example#key-1"),
    ):
        tampered = copy.deepcopy(signed)
        tampered["proof"][field] = bad_val
        assert verify_credential(tampered, pub_bytes) is False
