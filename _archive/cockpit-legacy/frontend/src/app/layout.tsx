import type { Metadata } from "next";
import "./globals.css";
import { SentryInit } from "@/components/SentryInit";

export const metadata: Metadata = {
  title: "LaneCore AI — Bauunternehmer-Cockpit",
  description: "Automatische Bauplan-Analyse und Massenermittlung für Trockenbauer",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="de">
      <body>
        <SentryInit />
        {children}
      </body>
    </html>
  );
}
