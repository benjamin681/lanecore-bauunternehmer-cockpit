"""B+4.9 — Auto-Anlage von Customer + Project beim LV-Upload.

Aufgerufen aus dem LV-Parse-/Upload-Workflow nachdem
``lv.projekt_name`` und ``lv.auftraggeber`` aus dem LV-Header
extrahiert wurden. Logik:

1. Wenn ``lv.auftraggeber`` ein nicht-leerer String ist:
   Pruefe ob bereits Customer mit gleichem Namen + Tenant existiert
   (case-insensitive, getrimmt). Falls ja: nutzen. Falls nein:
   neuen Customer anlegen.

2. Wenn ``lv.projekt_name`` ein nicht-leerer String ist UND ein
   Customer existiert (entweder aus Schritt 1 oder bereits zuvor
   verknuepft): pruefe ob Project mit gleichem Namen + Tenant +
   Customer existiert. Falls ja: nutzen. Falls nein: neues Project
   anlegen.

3. ``lv.project_id`` wird auf das Project gesetzt.

Failure-Modi (alle nicht-fatal — der LV-Upload bleibt erfolgreich):
- Beide Header-Felder leer → ``lv.project_id`` bleibt NULL.
- Nur ``projekt_name`` ohne ``auftraggeber`` → kein Customer kann
  abgeleitet werden, daher kein Project. Im UI laesst sich das
  spaeter manuell zuordnen.
- DB-Fehler → Logging, kein Re-Raise.

Idempotent: mehrfache Aufrufe auf demselben LV haben dieselbe
Wirkung. Es entstehen keine Duplikate.
"""
from __future__ import annotations

import structlog
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.customer import Customer, Project
from app.models.lv import LV

log = structlog.get_logger()


def _norm(s: str | None) -> str:
    return (s or "").strip()


def _find_customer_by_name(
    db: Session, tenant_id: str, name: str
) -> Customer | None:
    return (
        db.query(Customer)
        .filter(
            Customer.tenant_id == tenant_id,
            func.lower(Customer.name) == name.lower(),
        )
        .first()
    )


def _find_project_by_name(
    db: Session,
    tenant_id: str,
    customer_id: str,
    name: str,
) -> Project | None:
    return (
        db.query(Project)
        .filter(
            Project.tenant_id == tenant_id,
            Project.customer_id == customer_id,
            func.lower(Project.name) == name.lower(),
        )
        .first()
    )


def autocreate_for_lv(db: Session, lv: LV) -> tuple[Customer | None, Project | None]:
    """Hauptfunktion. Wird vom LV-Upload-Endpoint aufgerufen, sobald
    der Parser ``lv.projekt_name`` / ``lv.auftraggeber`` befuellt hat.

    Returns:
        (customer, project) — beide koennen None sein. Die Funktion
        committed NICHT — der Caller entscheidet ueber Transaction-
        Boundary.
    """
    auftraggeber = _norm(lv.auftraggeber)
    projekt_name = _norm(lv.projekt_name)

    if not auftraggeber:
        log.info(
            "autocreate_skip_no_auftraggeber",
            lv_id=lv.id,
            projekt_name=projekt_name,
        )
        return None, None

    # 1. Customer
    customer = _find_customer_by_name(db, lv.tenant_id, auftraggeber)
    if customer is None:
        customer = Customer(
            tenant_id=lv.tenant_id,
            name=auftraggeber,
        )
        db.add(customer)
        db.flush()  # ID verfuegbar fuer Project-FK
        log.info("autocreate_customer", lv_id=lv.id, customer_id=customer.id, name=auftraggeber)

    # 2. Project — nur wenn auch ein Projekt-Name vorliegt
    project: Project | None = None
    if projekt_name:
        project = _find_project_by_name(
            db, lv.tenant_id, customer.id, projekt_name
        )
        if project is None:
            project = Project(
                tenant_id=lv.tenant_id,
                customer_id=customer.id,
                name=projekt_name,
                status="draft",
            )
            db.add(project)
            db.flush()
            log.info(
                "autocreate_project",
                lv_id=lv.id, project_id=project.id, name=projekt_name,
            )
        # 3. Verknuepfung
        if lv.project_id != project.id:
            lv.project_id = project.id

    return customer, project
