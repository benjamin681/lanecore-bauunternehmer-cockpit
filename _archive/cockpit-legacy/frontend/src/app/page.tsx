import Link from "next/link";

export default function Home() {
  return (
    <main className="min-h-screen flex items-center justify-center bg-white">
      <div className="text-center max-w-xl px-6">
        <h1 className="text-4xl font-bold text-gray-900 mb-4">
          LaneCore AI
        </h1>
        <p className="text-lg text-gray-600 mb-8">
          Bauplan-Analyse und Massenermittlung — automatisch, präzise, schnell.
        </p>
        <Link
          href="/dashboard"
          className="inline-block bg-primary-600 text-white px-8 py-3 rounded-lg text-lg font-medium hover:bg-primary-700 transition-colors"
        >
          Zum Dashboard
        </Link>
      </div>
    </main>
  );
}
