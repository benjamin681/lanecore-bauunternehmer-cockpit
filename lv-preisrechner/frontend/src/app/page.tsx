import Link from "next/link";
import { ArrowRight, FileCheck, ShieldCheck, Upload, Zap } from "lucide-react";
import { Button } from "@/components/ui/button";

export default function LandingPage() {
  return (
    <main className="min-h-screen bg-gradient-to-b from-white via-bauplan-50 to-white">
      {/* Header */}
      <header className="max-w-6xl mx-auto px-6 py-5 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="w-9 h-9 rounded-lg bg-bauplan-600 text-white grid place-items-center font-bold">
            LC
          </div>
          <span className="font-semibold text-slate-900">LV-Preisrechner</span>
        </div>
        <div className="flex items-center gap-3">
          <Link href="/login">
            <Button variant="ghost" size="sm">
              Anmelden
            </Button>
          </Link>
          <Link href="/register">
            <Button size="sm">Kostenlos starten</Button>
          </Link>
        </div>
      </header>

      {/* Hero */}
      <section className="max-w-6xl mx-auto px-6 pt-14 pb-20 text-center">
        <div className="inline-flex items-center gap-2 text-xs font-medium px-3 py-1 rounded-full bg-bauplan-100 text-bauplan-700 mb-6">
          <Zap className="w-3.5 h-3.5" /> Für Trockenbauer, die keine Zeit mehr mit Excel
          verlieren wollen
        </div>
        <h1 className="text-5xl md:text-6xl font-bold tracking-tight text-slate-900 leading-tight">
          LV rein,
          <br />
          <span className="text-bauplan-600">fertiges Angebot raus.</span>
        </h1>
        <p className="mt-6 text-xl text-slate-600 max-w-2xl mx-auto">
          Sie laden Ihr Leistungsverzeichnis hoch. Unser System matcht es gegen{" "}
          <strong>Ihre eigenen Einkaufspreise</strong>, kalkuliert EP und GP und liefert das
          ausgefüllte PDF zurück — in Minuten statt Stunden.
        </p>
        <div className="mt-10 flex items-center justify-center gap-3">
          <Link href="/register">
            <Button size="lg">
              Jetzt starten <ArrowRight className="w-4 h-4" />
            </Button>
          </Link>
          <Link href="/login">
            <Button variant="secondary" size="lg">
              Einloggen
            </Button>
          </Link>
        </div>
      </section>

      {/* Features */}
      <section className="max-w-6xl mx-auto px-6 pb-24 grid md:grid-cols-3 gap-6">
        <Feature
          icon={<Upload className="w-6 h-6" />}
          title="Ihre Preisliste"
          text="Sie laden Ihre eigene Händler-Preisliste hoch (Kemmler, Wölpert, Raab Karcher …). Wir parsen sie automatisch in Produkt-DNA-Einträge."
        />
        <Feature
          icon={<Zap className="w-6 h-6" />}
          title="LV-Matching in Sekunden"
          text="Claude erkennt jede LV-Position, matcht auf unser Trockenbau-Wissen (W112–W631, F30–F120) und berechnet EP und GP inklusive Zuschläge."
        />
        <Feature
          icon={<FileCheck className="w-6 h-6" />}
          title="PDF zurück"
          text="Am Ende bekommen Sie ein ausgefülltes, strukturiertes Angebot als PDF. Alles nachvollziehbar, alles verifizierbar."
        />
      </section>

      {/* Trust */}
      <section className="max-w-4xl mx-auto px-6 pb-24">
        <div className="rounded-2xl bg-white border border-slate-200 shadow-sm p-8 flex items-start gap-4">
          <ShieldCheck className="w-6 h-6 text-success-500 shrink-0 mt-1" />
          <div>
            <div className="font-semibold text-slate-900">Ihre Daten bleiben bei Ihnen.</div>
            <div className="text-sm text-slate-600 mt-1">
              Jede Preisliste ist nur in Ihrem Account sichtbar. Wir teilen nichts mit anderen
              Kunden. Kein Handwerker hat denselben Einkaufspreis — darum bringt jeder seine
              eigene Liste mit.
            </div>
          </div>
        </div>
      </section>
    </main>
  );
}

function Feature({
  icon,
  title,
  text,
}: {
  icon: React.ReactNode;
  title: string;
  text: string;
}) {
  return (
    <div className="rounded-xl bg-white border border-slate-200 p-6 shadow-sm">
      <div className="w-11 h-11 grid place-items-center rounded-lg bg-bauplan-50 text-bauplan-600 mb-4">
        {icon}
      </div>
      <h3 className="text-lg font-semibold text-slate-900">{title}</h3>
      <p className="mt-2 text-sm text-slate-600 leading-relaxed">{text}</p>
    </div>
  );
}
