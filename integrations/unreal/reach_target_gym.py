#!/usr/bin/env python3
"""Gymnasium-facing client for the Unreal Reach Target EnvServer (no second server).

With Unreal in Play and a static identity configured::

  python integrations/unreal/reach_target_app.py --init-identity  # once
  # Play in Unreal, then:
  python -c "from reach_target_gym import make_env; e=make_env(); print(e.reset()); e.close()"

This is a thin helper around ``rlmesh.numpy.RemoteEnv`` (via ``gym_common``).
The PoC claim is **RLMesh env in Unreal (Gym-style API)** — not a registered
Gymnasium env id.
"""

from __future__ import annotations

import sys
from pathlib import Path

_UNREAL_DIR = Path(__file__).resolve().parent
if str(_UNREAL_DIR) not in sys.path:
    sys.path.insert(0, str(_UNREAL_DIR))

from gym_common import make_remote_env, smoke_remote_env


def make_env(address: str | None = None, **remote_kwargs):
    """Connect to the serving Reach Target as ``rlmesh.numpy.RemoteEnv``."""
    return make_remote_env(address, **remote_kwargs)


def main(argv: list[str] | None = None) -> int:
    del argv  # unused; kept for CLI symmetry
    return smoke_remote_env()


if __name__ == "__main__":
    raise SystemExit(main())
