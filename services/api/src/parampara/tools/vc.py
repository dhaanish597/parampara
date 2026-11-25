"""W3C Data Integrity eddsa-jcs-2022 signing and verification (BUILD_PLAN 20.2)."""

from __future__ import annotations

import copy
import hashlib
from typing import Any

import base58
from nacl.exceptions import BadSignatureError
from nacl.signing import SigningKey, VerifyKey

from parampara.tools.jcs import canonicalize_bytes


def _hash_data(unsigned_vc: dict[str, Any], proof_config: dict[str, Any]) -> bytes:
    transformed = canonicalize_bytes(unsigned_vc)
    canonical_config = canonicalize_bytes(proof_config)
    return hashlib.sha256(canonical_config).digest() + hashlib.sha256(transformed).digest()


def sign_credential(
    *,
    unsigned_vc: dict[str, Any],
    signing_key: SigningKey,
    verification_method: str,
    created: str,
) -> dict[str, Any]:
    """Sign an unsigned VC dict using Data Integrity eddsa-jcs-2022 (BUILD_PLAN 20.2)."""
    doc = copy.deepcopy(unsigned_vc)
    doc.pop("proof", None)
    proof_body: dict[str, Any] = {
        "type": "DataIntegrityProof",
        "cryptosuite": "eddsa-jcs-2022",
        "created": created,
        "verificationMethod": verification_method,
        "proofPurpose": "assertionMethod",
    }
    proof_config = {**proof_body, "@context": doc["@context"]}
    digest = _hash_data(doc, proof_config)
    sig = signing_key.sign(digest).signature
    proof_body["proofValue"] = "z" + base58.b58encode(sig).decode("ascii")
    doc["proof"] = proof_body
    return doc


def verify_credential(signed_vc: dict[str, Any], public_key_bytes: bytes) -> bool:
    """Verify a signed VC dict against a 32-byte Ed25519 public key (BUILD_PLAN 20.2)."""
    proof = signed_vc.get("proof")
    if not isinstance(proof, dict):
        return False
    if (
        proof.get("type") != "DataIntegrityProof"
        or proof.get("cryptosuite") != "eddsa-jcs-2022"
        or proof.get("proofPurpose") != "assertionMethod"
    ):
        return False
    vm = proof.get("verificationMethod")
    issuer = signed_vc.get("issuer")
    issuer_id = issuer.get("id") if isinstance(issuer, dict) else issuer
    if not isinstance(vm, str) or (
        isinstance(issuer_id, str) and not vm.startswith(f"{issuer_id}#")
    ):
        return False
    proof_value = proof.get("proofValue")
    if not isinstance(proof_value, str) or not proof_value.startswith("z"):
        return False
    doc = {k: v for k, v in signed_vc.items() if k != "proof"}
    proof_config = {k: v for k, v in proof.items() if k != "proofValue"}
    proof_config["@context"] = doc.get("@context")
    try:
        sig = base58.b58decode(proof_value[1:])
        digest = _hash_data(doc, proof_config)
        VerifyKey(public_key_bytes).verify(digest, sig)
        return True
    except (BadSignatureError, ValueError, KeyError, TypeError):
        return False
