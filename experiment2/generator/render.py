"""Render the hidden canonical dataset into semantically equivalent source variants.

Produces:
  artifacts/corpus/<profile_id>.csv        -- agent-visible source files
  artifacts/corpus_manifest.json           -- HIDDEN labels, never shown to the agent
  artifacts/task_packet/                   -- exactly what the agent receives

The manifest carries, per variant:
    canonical_source, representation_family, expected_output,
    equivalent, ambiguity_expected
"""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

import pandas as pd

from canonical import CANONICAL_COLUMNS
from profiles import ALL_PROFILES, Profile
from vocabulary import (
    COUNTRY_STYLES,
    HEADER_STYLES,
    MONTH_STYLES_NEEDING_YEAR,
    MONTH_WITH_YEAR_SUFFIX,
    NBSP,
    LOSSY_NUMBER_STYLES,
    format_number,
    month_token,
    parse_number,
)

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "artifacts"
CORPUS = ARTIFACTS / "corpus"
PACKET = ARTIFACTS / "task_packet"


def _needs_year_column(style: str) -> bool:
    return style in MONTH_STYLES_NEEDING_YEAR and style not in MONTH_WITH_YEAR_SUFFIX


def _apply_cosmetics(df: pd.DataFrame, cosmetics: tuple[str, ...]) -> pd.DataFrame:
    out = df.copy()
    obj = out.select_dtypes(include=["object"]).columns
    for op in cosmetics:
        if op == "title_case_values":
            for c in obj:
                out[c] = out[c].map(lambda v: v.title() if isinstance(v, str) else v)
        elif op == "upper_values":
            for c in obj:
                out[c] = out[c].map(lambda v: v.upper() if isinstance(v, str) else v)
        elif op == "pad_whitespace":
            for c in obj:
                out[c] = out[c].map(lambda v: f"  {v} " if isinstance(v, str) else v)
        elif op == "nbsp_in_values":
            for c in obj:
                out[c] = out[c].map(
                    lambda v: v.replace(" ", NBSP) if isinstance(v, str) else v)
    return out


def render_equivalent(canon: pd.DataFrame, p: Profile, year: int) -> pd.DataFrame:
    h = HEADER_STYLES[p.header_lang]
    cmap = COUNTRY_STYLES[p.country_style]
    d = canon.copy()
    d["_month"] = d["period"].str.slice(5, 7).astype(int)
    d["_country"] = d["country"].map(cmap)
    d["_token"] = d["_month"].map(lambda m: month_token(m, year, p.month_style))
    d["_sales"] = d["sales"].map(lambda v: format_number(v, p.number_style))

    needs_year = _needs_year_column(p.month_style)

    if p.shape == "long":
        cols = {h["country"]: d["_country"], h["product"]: d["product_id"]}
        if needs_year:
            cols[h["year"]] = year
        cols[h["month"] if needs_year or p.month_style in MONTH_WITH_YEAR_SUFFIX
             else h["period"]] = d["_token"]
        cols[h["sales"]] = d["_sales"]
        return pd.DataFrame(cols)

    if p.shape == "period_value":
        cols = {}
        cols[h["month"] if needs_year else h["period"]] = d["_token"]
        if needs_year:
            cols[h["year"]] = year
        cols[h["product"]] = d["product_id"]
        cols[h["country"]] = d["_country"]
        cols[h["sales"]] = d["_sales"]
        return pd.DataFrame(cols)

    if p.shape == "wide":
        index = [h["country"], h["product"]] + ([h["year"]] if needs_year else [])
        wide = d.assign(**{h["country"]: d["_country"], h["product"]: d["product_id"]})
        if needs_year:
            wide[h["year"]] = year
        pivot = wide.pivot_table(
            index=index, columns="_token", values="_sales", aggfunc="first"
        )
        order = sorted(
            pivot.columns,
            key=lambda t: d.loc[d["_token"] == t, "_month"].iloc[0],
        )
        return pivot[order].reset_index()

    raise ValueError(f"unknown shape: {p.shape}")


def render_ambiguity(canon: pd.DataFrame, p: Profile, year: int) -> pd.DataFrame:
    """Ambiguity cases. Correct behaviour is escalation, not normalization."""
    h = HEADER_STYLES["en"]
    sub = canon[canon["period"].str.slice(5, 7).astype(int) <= 12].copy()

    if p.id == "A01":
        # NN/NN/2026 with both components <= 12 in every row: order unrecoverable.
        sub = sub[sub["period"].str.slice(5, 7).astype(int) <= 6].copy()
        day = (sub.groupby("product_id").cumcount() % 12) + 1
        month = sub["period"].str.slice(5, 7).astype(int)
        return pd.DataFrame({
            h["period"]: [f"{a:02d}/{b:02d}/{year}" for a, b in zip(day, month)],
            h["product"]: sub["product_id"].values,
            h["country"]: sub["country"].values,
            h["sales"]: [f"{v:.2f}" for v in sub["sales"]],
        })

    if p.id == "A02":
        # '1,234' throughout, with no row anywhere resolving the comma's role.
        vals = []
        for v in sub["sales"]:
            thousands = int(round(v)) * 1000 + 234
            vals.append(f"{thousands // 1000:d},{thousands % 1000:03d}")
        return pd.DataFrame({
            h["period"]: sub["period"].values,
            h["product"]: sub["product_id"].values,
            h["country"]: sub["country"].values,
            h["sales"]: vals,
        })

    if p.id == "A03":
        names = {"FI": "Finland", "CZ": "Bohemia", "SE": "Scandinavia", "DE": "Germany"}
        return pd.DataFrame({
            h["period"]: sub["period"].values,
            h["product"]: sub["product_id"].values,
            h["country"]: sub["country"].map(names).values,
            h["sales"]: [f"{v:.2f}" for v in sub["sales"]],
        })

    if p.id == "A04":
        forms = ["ART-1", "art0001", "ART‑0002", "Art 0003", "ART--0004"]
        ids = [forms[i % len(forms)] for i in range(len(sub))]
        return pd.DataFrame({
            h["period"]: sub["period"].values,
            h["product"]: ids,
            h["country"]: sub["country"].values,
            h["sales"]: [f"{v:.2f}" for v in sub["sales"]],
        })

    if p.id == "A05":
        names = {"FI": "Suomi", "CZ": "Tschechei", "SE": "Norlandia", "DE": "Deutschland"}
        return pd.DataFrame({
            h["period"]: sub["period"].values,
            h["product"]: sub["product_id"].values,
            h["country"]: sub["country"].map(names).values,
            h["sales"]: [f"{v:.2f}" for v in sub["sales"]],
        })

    raise ValueError(f"unknown ambiguity profile: {p.id}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--suffix", default="")
    ap.add_argument("--no-packet", action="store_true")
    args = ap.parse_args()
    sfx = args.suffix

    corpus_dir = ARTIFACTS / f"corpus{sfx}"
    canon = pd.read_csv(ARTIFACTS / f"canonical{sfx}.csv")
    cman = json.loads((ARTIFACTS / f"canonical{sfx}_manifest.json").read_text(encoding="utf-8"))
    year = int(cman["params"]["year"])

    if corpus_dir.exists():
        shutil.rmtree(corpus_dir)
    corpus_dir.mkdir(parents=True)

    entries = []
    for p in ALL_PROFILES:
        if p.split == "ambiguity":
            df = render_ambiguity(canon, p, year)
        else:
            df = render_equivalent(canon, p, year)
        df = _apply_cosmetics(df, p.cosmetics)

        # Integrity guard: an `equivalent=True` variant must not destroy
        # information. Without this, a lossy render is indistinguishable from an
        # agent failure and would be misattributed to the agent.
        if p.equivalent:
            if p.number_style in LOSSY_NUMBER_STYLES:
                raise SystemExit(
                    f"{p.id}: number_style {p.number_style!r} is lossy and cannot be "
                    f"used on an equivalent variant")
            for v in canon["sales"]:
                if abs(parse_number(format_number(v, p.number_style), p.number_style) - v) > 1e-9:
                    raise SystemExit(
                        f"{p.id}: number_style {p.number_style!r} does not round-trip "
                        f"value {v}")

        path = corpus_dir / f"{p.id}.csv"
        df.to_csv(path, index=False, sep=p.sep, lineterminator="\n", encoding="utf-8")

        entries.append({
            "profile_id": p.id,
            "file": path.name,
            "split": p.split,
            "canonical_source": f"artifacts/canonical{sfx}.csv",
            "representation_family": list(p.families),
            "shape": p.shape,
            "month_style": p.month_style,
            "header_lang": p.header_lang,
            "country_style": p.country_style,
            "number_style": p.number_style,
            "cosmetics": list(p.cosmetics),
            "separator": p.sep,
            "equivalent": p.equivalent,
            "ambiguity_expected": p.ambiguity_expected,
            "expected_behaviour": p.expected_behaviour,
            "expected_output": (
                f"artifacts/canonical{sfx}.csv" if p.expected_behaviour == "normalize" else None
            ),
            "n_rows_rendered": int(len(df)),
            "notes": p.notes,
        })

    manifest = {
        "hidden": True,
        "note": "Labels. NEVER expose any field of this file to the modelling agent.",
        "canonical_sha256": cman["sha256"],
        "n_variants": len(entries),
        "splits": {s: sum(1 for e in entries if e["split"] == s)
                   for s in ("dev", "heldout", "ambiguity")},
        "variants": entries,
    }
    (ARTIFACTS / f"corpus{sfx}_manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    # ---- task packet: only what the agent may see -----------------------
    if args.no_packet:
        print(f"variants: {len(entries)}  {manifest['splits']}  (no task packet written)")
        return 0
    if PACKET.exists():
        shutil.rmtree(PACKET)
    (PACKET / "sources").mkdir(parents=True)
    for e in entries:
        if e["split"] == "dev":
            shutil.copy2(corpus_dir / e["file"], PACKET / "sources" / e["file"])

    print(f"variants: {len(entries)}  {manifest['splits']}")
    print(f"task packet exposes {len(list((PACKET / 'sources').glob('*.csv')))} dev sources")
    for e in entries:
        print(f"  {e['profile_id']}  {e['split']:9s} {e['shape']:13s} "
              f"{e['month_style']:16s} {e['header_lang']:3s} "
              f"{e['country_style']:15s} {e['number_style']:9s} rows={e['n_rows_rendered']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
