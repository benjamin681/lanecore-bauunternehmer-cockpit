# Skill: Frontend UI/UX für Bauunternehmer

## Zielgruppe-Analyse

**Harun's Vater & seine Kalkulatoren:**
- 50+ Jahre alt, Desktop-Nutzer, kein Tech-Affinity
- Gewohnt: Excel, PDF-Reader, E-Mail
- Ungeduldig mit langen Ladezeiten und komplizierten UIs
- Vertraut Zahlen, misstraut "KI-Magie"
- Arbeitet am Schreibtisch, nicht mobil auf der Baustelle

**Design-Konsequenzen:**
- Desktop-first (min. 1280px), kein Mobile-Optimierungsfokus
- Große Schriften, klare Buttons (kein subtiles Icon-only)
- Zahlen immer mit Einheit (m², m, Stk) — nie nackt
- Konfidenz/Unsicherheit IMMER sichtbar — keine versteckten Fehler
- Ladezeiten: immer Feedback, nie blank screen

---

## Design-Prinzipien

### 1. Vertrauen durch Transparenz
```
SCHLECHT: "Analyse abgeschlossen. Wandfläche: 245m²"
GUT:      "Analyse abgeschlossen (Konfidenz: 94%)"
          "Wandfläche: 245m² ⚠️ 2 Bereiche unsicher — bitte prüfen"
```

### 2. Aktionen klar benennen
```
SCHLECHT: Icon-Buttons ohne Text, Hover-Tooltips
GUT:      "PDF hochladen", "Analyse starten", "Als Excel exportieren"
          Primär-Button: Blau, groß, eindeutig
```

### 3. Fehler erklären, nicht nur anzeigen
```
SCHLECHT: "Fehler 422"
GUT:      "Die PDF-Datei konnte nicht gelesen werden.
          → Bitte prüfen Sie, ob die Datei nicht passwortgeschützt ist.
          → Unterstützte Formate: PDF (max. 50MB)"
```

### 4. Zahlen formatieren
```tsx
// Immer lokalisiert (Deutsch)
const formatM2 = (val: number) =>
  `${val.toLocaleString("de-DE", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} m²`;

const formatM = (val: number) =>
  `${val.toLocaleString("de-DE", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} m`;
```

---

## Farb-System

```css
/* Primärfarben */
--blue-primary: #2563EB;     /* Haupt-Aktionen */
--blue-light: #EFF6FF;       /* Hintergründe */

/* Status-Farben */
--green-success: #16A34A;    /* Analyse erfolgreich */
--yellow-warning: #D97706;   /* Unsichere Bereiche */
--red-error: #DC2626;        /* Fehler */

/* Neutral */
--gray-900: #111827;         /* Haupttext */
--gray-500: #6B7280;         /* Metadaten */
--gray-100: #F3F4F6;         /* Hintergründe */
--white: #FFFFFF;            /* Cards */
```

---

## Komponenten-Patterns

### Upload-Zone
```tsx
// Klare Drag-and-Drop Zone mit Status-Feedback
<div className="border-2 border-dashed border-gray-300 rounded-lg p-12 text-center hover:border-blue-400 transition-colors">
  <Upload className="mx-auto h-12 w-12 text-gray-400 mb-4" />
  <p className="text-lg font-medium text-gray-900">Bauplan hier ablegen</p>
  <p className="text-sm text-gray-500 mt-1">PDF bis 50MB • Grundrisse, Schnitte</p>
  <Button className="mt-4" onClick={triggerFileInput}>
    Datei auswählen
  </Button>
</div>
```

### Konfidenz-Anzeige
```tsx
function KonfidenzBadge({ wert }: { wert: number }) {
  const percent = Math.round(wert * 100);
  const color = percent >= 90 ? "green" : percent >= 70 ? "yellow" : "red";

  return (
    <span className={`inline-flex items-center gap-1 px-2 py-1 rounded text-sm font-medium
      ${color === "green" ? "bg-green-100 text-green-800" :
        color === "yellow" ? "bg-yellow-100 text-yellow-800" :
        "bg-red-100 text-red-800"}`}>
      {percent >= 90 ? "✓" : "⚠"} Konfidenz: {percent}%
    </span>
  );
}
```

### Ergebnis-Tabelle
```tsx
// Übersichtliche Massenermittlung mit Drill-Down
<Table>
  <TableHeader>
    <TableRow>
      <TableHead>Wandtyp</TableHead>
      <TableHead className="text-right">Länge</TableHead>
      <TableHead className="text-right">Fläche</TableHead>
      <TableHead>Status</TableHead>
    </TableRow>
  </TableHeader>
  <TableBody>
    {waende.map(wand => (
      <TableRow key={wand.id} className="cursor-pointer hover:bg-gray-50">
        <TableCell className="font-medium">{wand.typ}</TableCell>
        <TableCell className="text-right">{formatM(wand.laenge_m)}</TableCell>
        <TableCell className="text-right">{formatM2(wand.flaeche_m2)}</TableCell>
        <TableCell>
          {wand.unsicher && <Badge variant="warning">Prüfen</Badge>}
        </TableCell>
      </TableRow>
    ))}
  </TableBody>
</Table>
```

---

## Lade-States

```tsx
// Analyse-Fortschritt — nicht einfach ein Spinner
function AnalyseProgress({ phase, progress }: { phase: string; progress: number }) {
  const phasen = [
    { id: "upload", label: "PDF wird geladen" },
    { id: "scan", label: "Seiten werden erkannt" },
    { id: "analyse", label: "KI analysiert Grundriss" },
    { id: "validate", label: "Ergebnisse werden geprüft" },
  ];

  return (
    <div className="space-y-4">
      <Progress value={progress} className="h-3" />
      <p className="text-center text-gray-600">{phase} ... {progress}%</p>
      <div className="grid grid-cols-4 gap-2">
        {phasen.map(p => (
          <div key={p.id} className={`text-xs text-center p-2 rounded ${p.id === phase ? "bg-blue-100 text-blue-800" : "text-gray-400"}`}>
            {p.label}
          </div>
        ))}
      </div>
      <p className="text-xs text-center text-gray-400">
        Typische Analysedauer: 1–3 Minuten pro Seite
      </p>
    </div>
  );
}
```
