#!/usr/bin/env python3
"""Streamlit wrapper for the Fleet System Map component.

Follows `food-prep`'s `ui/taste_circle.py` exactly: a static, no-build component
that renders with a vendored vis-network and posts node clicks back over the
component v1 postMessage protocol. No CDN, no npm step.

`vis-network.min.js` is COPIED next to `index.html` rather than referenced from
the other repo, so this console has no dependency on where that repo lives.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

import streamlit.components.v1 as components

_FRONTEND_DIR = Path(__file__).parent / "system_map_component"

_system_map = components.declare_component("fleet_system_map",
                                           path=str(_FRONTEND_DIR))


def system_map(nodes: list[dict[str, Any]], edges: list[dict[str, Any]], *,
               height: int = 700, key: str) -> Optional[dict[str, Any]]:
    """Render the map and return the latest click.

    `{"id": <node id or None>, "t": <js ms>}` after each click on a clickable
    node, or on blank canvas where `id` is None; `None` before the first click.
    The timestamp makes repeated clicks on one node all deliver, which is what
    lets a click drive a selection.
    """
    return _system_map(nodes=nodes, edges=edges, height=height, key=key,
                       default=None)
