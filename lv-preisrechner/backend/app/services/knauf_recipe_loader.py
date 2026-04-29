"""Knauf-Rezept-Loader (B+4.13 Iter 5b 2026-04-29).

Laedt Knauf-System-Rezepte aus YAML-Dateien in `backend/data/knauf_systeme/`.
Diese YAMLs sind die strukturierte Repraesentation der oeffentlichen
Knauf-Detailblaetter (W11.de, W62.de, D11.de, F12) und enthalten:

- Material-Mengen pro m² (verified, derived, oder industry_standard)
- Befestigungsabstaende (verified aus Detailblaettern)
- Achsabstaende (verified aus Wandhoehen-Tabellen)
- Quellenangabe pro System (PDF + Seite + Abruf-Datum)

Der Loader ist additiv: er gibt zusaetzliche Knauf-Quellen-Metadaten
zurueck, ueberschreibt aber NICHT die produktiven Rezepte in
`materialrezepte.py`. Die Rezepte dort sind weiterhin die Quelle der
Wahrheit fuer die Kalkulation, da sie:
- ggf. Praxis-Anker von Harun's Vater enthalten,
- mat_nr-Felder fuer den supplier_price-Lookup tragen,
- ein konsistentes MaterialBedarf-Schema haben.

Die YAML-Dateien dienen als oeffentlich-belegte Quelle, gegen die die
produktiven Rezepte gepruefst werden koennen (Audit-Funktion). Bei
zukuenftigen Rezept-Aenderungen sollte stets ein Verweis auf die
YAML-Datei erfolgen, in der die Knauf-Quelle dokumentiert ist.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None


KNAUF_DATA_DIR = Path(__file__).parent.parent.parent / "data" / "knauf_systeme"


@dataclass
class KnaufSystemSpec:
    """Strukturierte Repraesentation eines Knauf-Systems aus YAML."""

    system_id: str
    bezeichnung: str
    quelle_dokument: str
    quelle_pdf: str
    quelle_abgerufen: str
    quelle_seiten: list[int] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def has_befestigung_verified(self) -> bool:
        b = self.raw.get("befestigung") or {}
        return b.get("quelle_status") == "verified"

    @property
    def has_unterkonstruktion_verified(self) -> bool:
        u = self.raw.get("unterkonstruktion") or {}
        if isinstance(u, dict):
            for v in u.values():
                if isinstance(v, dict) and v.get("quelle_status") == "verified":
                    return True
        return False


def load_all_knauf_systems() -> dict[str, KnaufSystemSpec]:
    """Laedt alle YAML-Dateien aus knauf_systeme/.

    Bei Multi-Variant-YAMLs (z.B. w620_w625_w626_w627.yaml mit `variants`-
    Schluessel) werden alle Varianten als separate Specs zurueckgegeben.
    """
    if yaml is None:
        return {}
    if not KNAUF_DATA_DIR.exists():
        return {}

    specs: dict[str, KnaufSystemSpec] = {}
    for yf in sorted(KNAUF_DATA_DIR.glob("*.yaml")):
        try:
            with open(yf, encoding="utf-8") as f:
                d = yaml.safe_load(f) or {}
        except Exception:
            continue

        # Multi-variant-Datei
        if "variants" in d and isinstance(d["variants"], list):
            shared_quelle = d.get("quelle") or {}
            for var in d["variants"]:
                if not isinstance(var, dict) or not var.get("system_id"):
                    continue
                merged = dict(var)
                if "quelle" not in merged:
                    merged["quelle"] = shared_quelle
                specs[var["system_id"]] = _build_spec(merged)
        # Single-system-Datei
        elif d.get("system_id"):
            specs[d["system_id"]] = _build_spec(d)

    return specs


def _build_spec(d: dict[str, Any]) -> KnaufSystemSpec:
    q = d.get("quelle") or {}
    return KnaufSystemSpec(
        system_id=d.get("system_id", "?"),
        bezeichnung=d.get("bezeichnung", ""),
        quelle_dokument=q.get("dokument", ""),
        quelle_pdf=q.get("pdf", ""),
        quelle_abgerufen=q.get("abgerufen", ""),
        quelle_seiten=q.get("seiten") or [],
        raw=d,
    )


def get_recipe_provenance(system_id: str) -> str | None:
    """Liefert eine kompakte Quellen-Beschreibung fuer einen System-ID,
    geeignet fuer Logs / Reports / Audits.

    Beispiel-Rueckgabe:
        "W628B aus Knauf W62.de Detailblatt 03/2020 (Seiten 10, 11, 35),
         abgerufen 2026-04-29"
    """
    specs = load_all_knauf_systems()
    s = specs.get(system_id)
    if s is None:
        return None
    seiten_str = (
        f" (Seiten {', '.join(str(p) for p in s.quelle_seiten)})"
        if s.quelle_seiten
        else ""
    )
    abgerufen_str = (
        f", abgerufen {s.quelle_abgerufen}" if s.quelle_abgerufen else ""
    )
    # YAML kann das Datum als datetime.date parsen — als ISO-String formatieren
    abgerufen_str = abgerufen_str.replace(
        f"{s.quelle_abgerufen!r}", str(s.quelle_abgerufen)
    )
    return (
        f"{s.system_id} aus {s.quelle_dokument}{seiten_str}{abgerufen_str}"
    )
