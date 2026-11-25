"""Ed25519 Multikey encoding, decoding, and DID document builder (BUILD_PLAN 20.1)."""

from __future__ import annotations

import base64
from typing import Any

import base58
from nacl.signing import SigningKey

ED25519_MULTICODEC_PREFIX = bytes([0xED, 0x01])


def keypair_from_seed_b64(seed_b64: str) -> tuple[SigningKey, bytes]:
    """Derive Ed25519 SigningKey and 32-byte public key from a base64 32-byte seed."""
    seed = base64.b64decode(seed_b64)
    if len(seed) != 32:
        raise ValueError(f"Expected 32-byte Ed25519 seed, got {len(seed)} bytes")
    signing_key = SigningKey(seed)
    return signing_key, bytes(signing_key.verify_key)


def encode_public_multikey(public_key_bytes: bytes) -> str:
    """Encode 32-byte Ed25519 public key as multibase 'z' + base58btc(0xed 0x01 + pubkey)."""
    if len(public_key_bytes) != 32:
        raise ValueError(f"Expected 32-byte public key, got {len(public_key_bytes)}")
    encoded = base58.b58encode(ED25519_MULTICODEC_PREFIX + public_key_bytes).decode("ascii")
    return f"z{encoded}"


def decode_public_multikey(multibase: str) -> bytes:
    """Decode multibase 'z...' Ed25519 Multikey string back to 32 raw public key bytes."""
    if not multibase.startswith("z"):
        raise ValueError("Multikey must start with multibase prefix 'z'")
    raw = base58.b58decode(multibase[1:])
    if len(raw) != 34 or raw[:2] != ED25519_MULTICODEC_PREFIX:
        raise ValueError("Invalid Ed25519 Multikey header or length")
    return raw[2:]


def build_did_document(
    *,
    issuer_did: str,
    key_id: str,
    public_key_bytes: bytes,
) -> dict[str, Any]:
    """Build W3C DID document for did:web issuer (BUILD_PLAN 20.1)."""
    vm_id = f"{issuer_did}#{key_id}"
    return {
        "@context": [
            "https://www.w3.org/ns/did/v1",
            "https://w3id.org/security/multikey/v1",
        ],
        "id": issuer_did,
        "verificationMethod": [
            {
                "id": vm_id,
                "type": "Multikey",
                "controller": issuer_did,
                "publicKeyMultibase": encode_public_multikey(public_key_bytes),
            }
        ],
        "assertionMethod": [vm_id],
    }
