/**
 * Sentry setup — initialized only when NEXT_PUBLIC_SENTRY_DSN is set.
 *
 * Using a lightweight direct import instead of @sentry/nextjs wrappers
 * to keep bundle size minimal. Call `initSentry()` from the layout.
 */

let initialized = false;

export async function initSentry() {
  if (initialized) return;
  if (typeof window === "undefined") return;
  const dsn = process.env.NEXT_PUBLIC_SENTRY_DSN;
  if (!dsn) return;

  try {
    const Sentry = await import("@sentry/nextjs");
    Sentry.init({
      dsn,
      environment: process.env.NODE_ENV,
      tracesSampleRate: 0.1,
      replaysOnErrorSampleRate: 1.0,
      replaysSessionSampleRate: 0,
    });
    initialized = true;
    // eslint-disable-next-line no-console
    console.log("[sentry] initialized");
  } catch (err) {
    // eslint-disable-next-line no-console
    console.warn("[sentry] init failed", err);
  }
}
