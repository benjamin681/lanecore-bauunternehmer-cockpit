# Skill: Next.js 14 Frontend (App Router)

## Ordnerstruktur

```
src/
├── app/
│   ├── layout.tsx              # Root Layout (Clerk Provider, Theme)
│   ├── page.tsx                # Landing / Login-Redirect
│   ├── (auth)/
│   │   ├── sign-in/page.tsx
│   │   └── sign-up/page.tsx
│   └── (dashboard)/
│       ├── layout.tsx          # Dashboard-Shell (Sidebar, Header)
│       ├── page.tsx            # Dashboard-Übersicht
│       ├── projekte/
│       │   ├── page.tsx        # Projekt-Liste
│       │   ├── [id]/page.tsx   # Projekt-Detail
│       │   └── neu/page.tsx    # Neues Projekt
│       └── analyse/
│           ├── upload/page.tsx # PDF-Upload
│           └── [jobId]/page.tsx # Analyse-Ergebnis
├── components/
│   ├── ui/                     # shadcn/ui Basis-Komponenten
│   ├── bauplan/
│   │   ├── UploadZone.tsx
│   │   ├── AnalyseProgress.tsx
│   │   └── ErgebnisTabelle.tsx
│   └── layout/
│       ├── Sidebar.tsx
│       └── Header.tsx
├── lib/
│   ├── api.ts                  # Backend-API-Client
│   ├── utils.ts                # clsx, tailwind-merge
│   └── validations.ts          # Zod-Schemas
└── types/
    └── index.ts                # TypeScript-Typen
```

---

## Server vs. Client Components

```tsx
// SERVER Component (Standard, kein "use client")
// Gut für: Datenabruf, statische Inhalte, SEO
async function ProjektDetail({ params }: { params: { id: string } }) {
  const projekt = await getProjekt(params.id); // Direkter DB-Zugriff oder API-Call
  return <div>{projekt.name}</div>;
}

// CLIENT Component ("use client" erforderlich)
// Gut für: Events, useState, Browser-APIs
"use client";
function UploadZone() {
  const [isDragging, setIsDragging] = useState(false);
  return <div onDragOver={() => setIsDragging(true)}>...</div>;
}
```

---

## PDF-Upload mit Server Action

```tsx
// app/(dashboard)/analyse/upload/page.tsx
"use server";

import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";

async function uploadBauplan(formData: FormData) {
  "use server"; // Server Action

  const file = formData.get("file") as File;
  const arrayBuffer = await file.arrayBuffer();

  // Direkt zum Backend-API
  const response = await fetch(`${process.env.BACKEND_URL}/api/v1/bauplan/upload`, {
    method: "POST",
    body: formData,
    headers: { Authorization: `Bearer ${await getAuthToken()}` },
  });

  const { job_id } = await response.json();
  redirect(`/analyse/${job_id}`);
}

export default function UploadPage() {
  return (
    <form action={uploadBauplan}>
      <input type="file" name="file" accept=".pdf" required />
      <button type="submit">Analyse starten</button>
    </form>
  );
}
```

---

## Polling für Analyse-Status

```tsx
// app/(dashboard)/analyse/[jobId]/page.tsx
"use client";

import { useEffect, useState } from "react";

export default function AnalysePage({ params }: { params: { jobId: string } }) {
  const [status, setStatus] = useState<"pending" | "processing" | "completed" | "failed">("pending");
  const [progress, setProgress] = useState(0);

  useEffect(() => {
    if (status === "completed" || status === "failed") return;

    const interval = setInterval(async () => {
      const res = await fetch(`/api/bauplan/${params.jobId}/status`);
      const data = await res.json();
      setStatus(data.status);
      setProgress(data.progress);
    }, 2000); // Alle 2 Sekunden

    return () => clearInterval(interval);
  }, [status, params.jobId]);

  if (status === "pending") return <div>Analyse wird gestartet...</div>;
  if (status === "processing") return <AnalyseProgress progress={progress} />;
  if (status === "completed") return <ErgebnisAnzeige jobId={params.jobId} />;
  return <div>Fehler bei der Analyse.</div>;
}
```

---

## Clerk Auth Integration

```tsx
// middleware.ts (Root-Level)
import { clerkMiddleware, createRouteMatcher } from "@clerk/nextjs/server";

const isPublicRoute = createRouteMatcher(["/", "/sign-in(.*)", "/sign-up(.*)"]);

export default clerkMiddleware((auth, req) => {
  if (!isPublicRoute(req)) auth().protect();
});

export const config = {
  matcher: ["/((?!_next|[^?]*\\.(?:html?|css|js(?!on)|jpe?g|webp|png|gif|svg|ttf|woff2?|ico|csv|docx?|xlsx?|zip|webmanifest)).*)", "/(api|trpc)(.*)"],
};
```

---

## Zod-Validierung für Formulare

```tsx
import { z } from "zod";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";

const projektSchema = z.object({
  name: z.string().min(3, "Mindestens 3 Zeichen").max(100),
  beschreibung: z.string().optional(),
  auftraggeber: z.string().min(2, "Auftraggeber ist Pflicht"),
});

type ProjektForm = z.infer<typeof projektSchema>;

function NeueProjektForm() {
  const form = useForm<ProjektForm>({
    resolver: zodResolver(projektSchema),
  });

  async function onSubmit(data: ProjektForm) { ... }
  return <form onSubmit={form.handleSubmit(onSubmit)}>...</form>;
}
```
