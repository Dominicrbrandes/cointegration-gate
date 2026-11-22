"""Load config.yaml. Centralized so every module reads the same source of truth."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import yaml

# SHA-256 over the canonical JSON of the loaded config, excluding the keys listed
# in FINGERPRINT_EXCLUDE below. This is the ex-ante methodology lock in machine-
# checkable form: every number the paper reports was produced under this exact
# configuration.
#
# If you legitimately change a locked value, this constant MUST be updated in the
# same commit AND the change recorded in CHANGELOG.md with the reason and the
# resulting number movements. That pairing is the point - the assertion exists so
# that a config change cannot happen silently, not to prevent config changes.
LOCKED_CONFIG_SHA256 = "22ff4a2fe3cc5423530ae8f658830fe83c5d00e1e0500610210ececa721840f4"

# Keys that describe where output goes rather than what is computed. Changing an
# output path does not invalidate a result, so it should not trip the lock.
FINGERPRINT_EXCLUDE = {"paths", "output"}


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def load_config(path: Path | str | None = None, *, verify: bool = True) -> dict:
    """Load config.yaml and, by default, assert the methodology lock.

    Verifying here rather than in a single stage means the lock covers the whole
    pipeline: stages 1-4 produce Tables 1, 2, and 3, so a check that fired only
    at stage 5 would let a mutated config regenerate three of the paper's six
    tables silently before anything failed.

    `verify=False` exists for tooling that legitimately loads a modified config
    (parameter sweeps, the orientation robustness script's pinned variants).
    """
    if path is None:
        path = repo_root() / "config.yaml"
    with open(path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    if verify:
        verify_config_lock(cfg)
    return cfg


def config_fingerprint(cfg: dict) -> str:
    """Stable hash of the methodology-bearing config values.

    Hashes the parsed structure rather than the file bytes, so reformatting,
    comment edits, and line-ending changes do not trip the lock - only a change
    to a value that feeds a computation does.
    """
    material = {k: v for k, v in cfg.items() if k not in FINGERPRINT_EXCLUDE}
    canonical = json.dumps(material, sort_keys=True, separators=(",", ":"),
                           default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def verify_config_lock(cfg: dict, *, strict: bool = True) -> str:
    """Assert the running config matches the locked fingerprint.

    Raises RuntimeError on mismatch. Without this, a clone with a mutated
    `config.yaml` regenerates the entire pipeline self-consistently and every
    downstream reproducibility assertion passes - on numbers that do not match
    the paper. The internal-consistency checks cannot catch that class of drift
    on their own, because they recompute under the same mutated config they are
    checking.
    """
    actual = config_fingerprint(cfg)
    if LOCKED_CONFIG_SHA256 == "PLACEHOLDER":
        raise RuntimeError(
            "LOCKED_CONFIG_SHA256 is unset in src/config_io.py. Set it to:\n"
            f"    {actual}"
        )
    if actual != LOCKED_CONFIG_SHA256:
        msg = (
            "config.yaml does not match the locked methodology fingerprint.\n"
            f"  expected : {LOCKED_CONFIG_SHA256}\n"
            f"  actual   : {actual}\n"
            "Every number in paper/pairs_stat_arb.md was generated under the "
            "expected configuration. If this change is intended, update "
            "LOCKED_CONFIG_SHA256 in src/config_io.py and record the change in "
            "CHANGELOG.md with the reason and the resulting number movements."
        )
        if strict:
            raise RuntimeError(msg)
        print("WARNING: " + msg)
    return actual
