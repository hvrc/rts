# Stage 1: Build the static Vite app.
# VITE_API_URL is the backend base URL, baked in at build time (see src/components/chat.tsx).
# Override with: docker build --build-arg VITE_API_URL=https://<backend> .
FROM node:20-alpine AS builder
RUN apk add --no-cache libc6-compat
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm ci || npm install
COPY . .
# Default matches deploy.sh's default backend (the service's own run.app URL). deploy.sh
# passes --set-build-env-vars to override it; this value is only the standalone-build
# fallback. Keep the two in step, or a manual `docker build` ships the wrong backend.
ARG VITE_API_URL=https://rts-backend-em6d5d3fha-ue.a.run.app
ENV VITE_API_URL=$VITE_API_URL
RUN npm run build

# Stage 2: Serve the static build (SPA history-fallback).
FROM node:20-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production
ENV PORT=8080
RUN npm install -g serve@14
COPY --from=builder /app/dist ./dist
EXPOSE 8080
CMD ["sh", "-c", "serve -s dist -l ${PORT:-8080}"]
