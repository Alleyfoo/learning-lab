#!/usr/bin/env python3
"""AppTest smoke test for the v0.5 System Map operating surface.

AppTest cannot drive the vis-network click, so map selection is simulated by
pre-setting `st.session_state["map_selection"]` (typed selection, the same key
`_render_system_map` reads) before `run()`. For the worker panel we pre-set
`map_pick` (the bare worker name the existing worker panel reads). Each case
asserts that the type-appropriate panel expander renders -- i.e. that the typed
dispatch in `_render_typed_panel` lands the right panel for each node kind
without raising.

Run:  python supervisor/test_app.py --self-test
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
LAB = HERE.parent
sys.path.insert(0, str(LAB / "fleet"))
sys.path.insert(0, str(HERE))

from streamlit.testing.v1 import AppTest  # noqa: E402

import fleet       # noqa: E402  (discover real worker names / scopes / sources)
import system_map  # noqa: E402

APP = HERE / "app.py"
DEFAULT_TIMEOUT = 30


def _expander_present(at, label: str) -> bool:
    """True if an expander whose label equals `label` rendered.

    In this Streamlit version `at.expander` is a list of expander elements,
    each carrying a `.label` -- not a callable query. Match by exact label.
    """
    return any(getattr(e, "label", None) == label for e in at.expander)


def _pick_selections():
    """Find one real selection of each kind from the live fleet."""
    workers = fleet.load_all()
    by_name = {w.name: w for w in workers}

    # inbox: any established worker has an input node
    inbox = {"kind": "inbox", "worker": workers[0].name} if workers else None

    # company: a real scope (customer) that exists on disk
    company = None
    for w in workers:
        sc = system_map.scope_of(w)
        if sc:
            company = {"kind": "company", "company": sc}
            break

    # source: a worker + one of its source collections (provenance panel)
    source = None
    for w in workers:
        srcs = list((w.model.get("sources") or {}).keys())
        if srcs:
            source = {"kind": "source", "worker": w.name, "source": srcs[0]}
            break

    # destination: a real declared destination if any worker has one; else an
    # arbitrary key to exercise the truthful empty-feeds caption.
    dest_worker = next((w for w in workers if w.destination), None)
    if dest_worker:
        destination = {"kind": "destination",
                       "key": system_map.destination_key(dest_worker.destination)}
    else:
        destination = {"kind": "destination", "key": "destination:finance:reskontra"}

    # worker: the bare-name map_pick the existing worker panel reads
    worker_pick = workers[0].name if workers else None

    return inbox, company, source, destination, worker_pick


def _run_with(selection=None, pick=None) -> AppTest:
    at = AppTest.from_file(str(APP), default_timeout=DEFAULT_TIMEOUT)
    if selection is not None:
        at.session_state["map_selection"] = selection
    if pick is not None:
        at.session_state["map_pick"] = pick
    at.run()
    return at


def _self_test() -> int:
    failures: list[str] = []

    def check(cond: bool, msg: str) -> None:
        if not cond:
            failures.append(msg)

    inbox, company, source, destination, worker_pick = _pick_selections()

    # --- no selection: the app still renders cleanly -------------------------
    at = _run_with()
    check(not at.exception, f"bare render raised: {[str(e) for e in at.exception]}")

    # --- inbox panel (acceptance A surface) ----------------------------------
    if inbox:
        at = _run_with(selection=inbox)
        check(not at.exception,
              f"inbox selection raised: {[str(e) for e in at.exception]}")
        check(_expander_present(at, f"Inbox: {inbox['worker']}"),
              f"inbox panel expander missing for {inbox['worker']}")

    # --- v0.6 Phase 7: the operator binding surface (sole + shared) --------
    # AppTest cannot drive the file_uploader, so the operator's slot choice is
    # simulated via session_state (the selectbox key the inbox panel reads).
    by_name = {w.name: w for w in fleet.load_all()}
    acme = by_name.get("acme-august-recon")
    fazerish = by_name.get("fazerish-invoicing")

    def _has_selectbox(at_, label):
        return any(getattr(s, "label", None) == label for s in at_.selectbox)

    def _has_caption_containing(at_, needle):
        return any(needle in str(getattr(c, "value", "")) for c in at_.caption)

    if acme:
        sel = {"kind": "inbox", "worker": "acme-august-recon"}
        at = _run_with(selection=sel)
        # simulate the operator binding the next upload to the `statement` slot
        at.session_state["inbox_slot_acme-august-recon"] = "statement"
        at.run()
        check(not at.exception,
              f"acme inbox (sole slots) raised: {[str(e) for e in at.exception]}")
        check(_has_selectbox(at, "Bind to slot"),
              "acme inbox panel offers a slot picker for its sole slots")
        check(not _has_caption_containing(at, "Shared slots"),
              "a sole-slot worker does not show the shared-slots caption")

    if fazerish:
        sel = {"kind": "inbox", "worker": "fazerish-invoicing"}
        at = _run_with(selection=sel)
        check(not at.exception,
              f"fazerish inbox (shared slots) raised: {[str(e) for e in at.exception]}")
        check(_has_caption_containing(at, "Shared slots"),
              "fazerish inbox panel shows the shared-slots caption (one upload binds all)")
        check(not _has_selectbox(at, "Bind to slot"),
              "a shared-slot worker does not offer a slot picker")

    # --- company panel (acceptance B surface) --------------------------------
    if company:
        at = _run_with(selection=company)
        check(not at.exception,
              f"company selection raised: {[str(e) for e in at.exception]}")
        check(_expander_present(at, f"Company: {company['company']}"),
              f"company panel expander missing for {company['company']}")

    # --- source provenance panel (item 9) ------------------------------------
    if source:
        at = _run_with(selection=source)
        check(not at.exception,
              f"source selection raised: {[str(e) for e in at.exception]}")
        check(_expander_present(at, f"Source: {source['source']}"),
              f"source panel expander missing for {source['source']}")

    # --- destination panel (the D canary surface) ----------------------------
    at = _run_with(selection=destination)
    check(not at.exception,
          f"destination selection raised: {[str(e) for e in at.exception]}")
    check(_expander_present(at, "Destination"),
          "destination panel expander missing")

    # --- worker panel (acceptance E: unchanged path via map_pick) ------------
    if worker_pick:
        at = _run_with(pick=worker_pick)
        check(not at.exception,
              f"worker pick raised: {[str(e) for e in at.exception]}")
        # the worker panel does not use a typed expander; assert the worker name
        # appears somewhere in the rendered markdown so we know it rendered.
        md_blob = "\n".join(str(m.value) for m in at.markdown)
        check(worker_pick in md_blob,
              f"worker panel did not surface worker name {worker_pick!r}")

    if failures:
        sys.stderr.write("SELF-TEST FAILED:\n  " + "\n  ".join(failures) + "\n")
        return 1
    print("SELF-TEST PASSED (AppTest: each map-selection kind renders its "
          "type-appropriate panel -- inbox / company / source / destination / "
          "worker -- with no exception / Phase 7: acme inbox offers a sole-slot "
          "picker (operator choice via session_state), fazerish inbox shows the "
          "shared-slots caption with no picker)")
    return 0


if __name__ == "__main__":
    raise SystemExit(_self_test() if sys.argv[1:2] == ["--self-test"] else 2)