# syntax=docker/dockerfile:1.6
#
# B+4.3.2b-1: Multi-Stage-Dockerfile fuer Next.js 14 (Hetzner-Deployment).
#
# Nutzt den Next.js standalone-Output: der finale Runtime-Layer hat nur
# ``.next/standalone/`` (inkl. minimalem ``node_modules``) + static-Assets
# + ``public``. Dadurch landet das Runtime-Image deutlich unter dem, was
# ein `npm run start`-basiertes Image braechte.
#
# Vercel-Parallel-Betrieb: ``output: "standalone"`` wird von Vercel
# ignoriert, der bestehende vercel.json-basierte Deploy-Flow bleibt
# funktionsfaehig.

# =========================================================================
# Stage 1 — Dependencies
# =========================================================================
FROM node:20-alpine AS deps

WORKDIR /app

# --legacy-peer-deps wegen @types/node@25 vs. Next.js 14-Pin (B+4.3.1a).
COPY package.json package-lock.json* ./
RUN npm ci --legacy-peer-deps

# =========================================================================
# Stage 2 — Build
# =========================================================================
FROM node:20-alpine AS builder

WORKDIR /app

ARG BACKEND_URL=http://backend:8000
ENV BACKEND_URL=${BACKEND_URL}
ENV NEXT_TELEMETRY_DISABLED=1 \
    NODE_ENV=production

COPY --from=deps /app/node_modules ./node_modules
COPY . .

RUN npm run build

# =========================================================================
# Stage 3 — Runtime
# =========================================================================
FROM node:20-alpine AS runtime

WORKDIR /app

ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000 \
    HOSTNAME=0.0.0.0

# Non-root User (alpine: addgroup/adduser)
RUN addgroup -g 1001 -S nodejs \
    && adduser -S -u 1001 -G nodejs nextjs

# Standalone-Output uebernehmen: server.js + minimal node_modules
# Hinweis: public/ existiert in diesem Projekt nicht (keine statischen
# Assets ausserhalb von src/), entsprechend kein COPY dafuer noetig.
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

USER nextjs

EXPOSE 3000

# wget kommt mit busybox in node:alpine, keine zusaetzliche Installation
# noetig. Wichtig: 127.0.0.1 (nicht localhost), weil BusyBox-wget sonst
# ueber [::1] laufen will, und Next.js mit HOSTNAME=0.0.0.0 lauscht nur
# IPv4 — sonst wird der Container faelschlicherweise als "unhealthy"
# markiert.
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD wget --no-verbose --tries=1 --spider "http://127.0.0.1:${PORT}/" || exit 1

CMD ["node", "server.js"]
