import type { Metadata } from "next";
import "./globals.css";

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
      <body>{children}</body>
    </html>
  );
}
