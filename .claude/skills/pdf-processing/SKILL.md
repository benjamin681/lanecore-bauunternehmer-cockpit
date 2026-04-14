# Skill: PDF-Processing

## PDF-Bibliotheken Übersicht

| Bibliothek | Stärke | Schwäche | Einsatz |
|-----------|--------|----------|---------|
| **pypdf** | Metadaten, Text-Extraktion | Kein Layout, kein OCR | Schnell-Check, Seitenanzahl |
| **pdfplumber** | Text + Tabellen mit Layout | Langsam, RAM-intensiv | Tabellen aus Preislisten |
| **pdf2image** | Hochwertige Bild-Konvertierung | Braucht poppler | Baupläne → Vision-API |
| **Pillow** | Bild-Nachbearbeitung | Kein PDF-Support | Kontrast, Schärfe verbessern |

---

## Bauplan-PDFs zu Bildern

```python
from pdf2image import convert_from_bytes
from PIL import Image, ImageEnhance
import io

def pdf_to_images(pdf_bytes: bytes, dpi: int = 200) -> list[Image.Image]:
    """
    Konvertiert PDF-Seiten zu Bildern für Claude Vision.

    DPI-Empfehlung:
    - 150 DPI: Schnell, für Übersichts-Check
    - 200 DPI: Standard für Bauplan-Analyse (guter Kompromiss)
    - 300 DPI: Bei schlechter Plan-Qualität oder sehr feinen Maßketten
    """
    images = convert_from_bytes(
        pdf_bytes,
        dpi=dpi,
        fmt="PNG",
        thread_count=4,
    )
    return images


def enhance_plan_image(img: Image.Image) -> Image.Image:
    """Verbessert Kontrast für bessere OCR-Ergebnisse."""
    # Kontrast erhöhen (Maßzahlen besser lesbar)
    img = ImageEnhance.Contrast(img).enhance(1.5)
    # Schärfe leicht erhöhen
    img = ImageEnhance.Sharpness(img).enhance(1.2)
    return img
```

---

## PDF-Metadaten und Vorprüfung

```python
import pypdf

def check_pdf(pdf_bytes: bytes) -> dict:
    """Schnell-Check eines PDFs vor der Vollanalyse."""
    reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))

    return {
        "num_pages": len(reader.pages),
        "is_encrypted": reader.is_encrypted,
        "has_text": any(
            page.extract_text().strip()
            for page in reader.pages[:3]  # Nur erste 3 Seiten prüfen
        ),
        "page_sizes": [
            {
                "width_mm": float(page.mediabox.width) * 0.352778,  # pt → mm
                "height_mm": float(page.mediabox.height) * 0.352778,
            }
            for page in reader.pages
        ],
    }

def classify_page_format(width_mm: float, height_mm: float) -> str:
    """DIN-Format aus Seitengröße ermitteln."""
    long_side = max(width_mm, height_mm)
    short_side = min(width_mm, height_mm)

    formats = {
        "A4": (297, 210),
        "A3": (420, 297),
        "A2": (594, 420),
        "A1": (841, 594),
        "A0": (1189, 841),
    }

    for name, (l, s) in formats.items():
        if abs(long_side - l) < 10 and abs(short_side - s) < 10:
            return name
    return "Custom"
```

---

## Preislisten-Extraktion mit pdfplumber

```python
import pdfplumber

def extract_price_table(pdf_bytes: bytes) -> list[dict]:
    """Extrahiert Preistabellen aus Lieferanten-PDFs."""
    rows = []

    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            tables = page.extract_tables({
                "vertical_strategy": "lines",
                "horizontal_strategy": "lines",
            })

            for table in tables:
                if not table or len(table) < 2:
                    continue

                headers = [str(h).strip().lower() for h in table[0]]
                for row in table[1:]:
                    if row and any(cell for cell in row):
                        rows.append(dict(zip(headers, [str(c or "").strip() for c in row])))

    return rows
```

---

## Dateigröße und Memory-Management

```python
MAX_PDF_MB = 50

def validate_pdf_size(pdf_bytes: bytes) -> None:
    size_mb = len(pdf_bytes) / (1024 * 1024)
    if size_mb > MAX_PDF_MB:
        raise ValueError(f"PDF zu groß: {size_mb:.1f}MB (Max: {MAX_PDF_MB}MB)")

# Bilder nicht alle gleichzeitig in Memory laden
def process_pages_lazy(pdf_bytes: bytes, dpi: int = 200):
    """Generator: Seite für Seite verarbeiten (Memory-effizient)."""
    reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
    for page_num in range(len(reader.pages)):
        # Nur eine Seite auf einmal konvertieren
        images = convert_from_bytes(
            pdf_bytes,
            dpi=dpi,
            first_page=page_num + 1,
            last_page=page_num + 1,
        )
        yield page_num, images[0]
        del images  # Memory freigeben
```

---

## S3-Upload für PDFs

```python
import aioboto3
from app.core.config import settings

async def upload_pdf_to_s3(pdf_bytes: bytes, job_id: str, filename: str) -> str:
    """Uploaded PDF zu S3, gibt die URL zurück."""
    key = f"uploads/{job_id}/{filename}"

    session = aioboto3.Session()
    async with session.client(
        "s3",
        region_name=settings.aws_region,
        aws_access_key_id=settings.aws_access_key_id,
        aws_secret_access_key=settings.aws_secret_access_key,
    ) as s3:
        await s3.put_object(
            Bucket=settings.s3_bucket_name,
            Key=key,
            Body=pdf_bytes,
            ContentType="application/pdf",
            ServerSideEncryption="AES256",  # Wichtig: Baupläne = sensibel
        )

    return f"s3://{settings.s3_bucket_name}/{key}"
```
