# ── EnergyBot Frontend — React/Vite → Nginx ──────────────────────────────────

# Stage 1: Build
FROM node:22-alpine AS builder
WORKDIR /app

# Empty string = nginx proxies /api/ to the backend container (default for Docker).
# Override with --build-arg VITE_API_BASE_URL=http://host:8000 for direct access.
ARG VITE_API_BASE_URL=""
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL

COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

# Stage 2: Serve with nginx
FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
