"""Trockenbau Knowledge Base — herstellergesicherte Materialdaten."""

import json
from pathlib import Path

_KB_PATH = Path(__file__).parent / "trockenbau_systeme.json"
_kb_cache: dict | None = None


def get_kb() -> dict:
    """Load the knowledge base (cached after first read)."""
    global _kb_cache
    if _kb_cache is None:
        _kb_cache = json.loads(_KB_PATH.read_text(encoding="utf-8"))
    return _kb_cache


def get_system(system_id: str) -> dict | None:
    """Get a wall or ceiling system by ID (e.g., 'W112', 'D112')."""
    kb = get_kb()
    if system_id.startswith("W") or system_id.startswith("w"):
        return kb["wandsysteme"].get(system_id.upper())
    elif system_id.startswith("D") or system_id.startswith("d"):
        return kb["deckensysteme"].get(system_id.upper())
    return None


def get_material_pro_m2(system_id: str) -> dict:
    """Get material consumption per m² for a system. Falls back to defaults."""
    system = get_system(system_id)
    if system:
        return system["material_pro_m2"]
    # Fallback: conservative defaults
    if system_id.upper().startswith("D"):
        return get_kb()["deckensysteme"]["D112"]["material_pro_m2"]
    return get_kb()["wandsysteme"]["W111"]["material_pro_m2"]


def get_verschnitt(system_id: str) -> dict:
    """Get waste factors for a system."""
    system = get_system(system_id)
    if system and "verschnitt" in system:
        return system["verschnitt"]
    return {"platten": 0.10, "profile": 0.05}


def get_vob_oeffnung_grenze() -> float:
    """Öffnungen bis zu dieser Größe werden nach VOB/C übermessen (kein Abzug)."""
    return get_kb()["normen"]["din_18340_vob_c"]["oeffnungen_uebermessen_bis_m2"]
