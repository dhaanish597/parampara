"""Print 32 random bytes, base64 encoded, for ISSUER_ED25519_SEED_B64."""

import base64
import secrets

print(base64.b64encode(secrets.token_bytes(32)).decode())
