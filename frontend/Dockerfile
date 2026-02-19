# --- STAGE 1 : Build ---
FROM alpine:latest AS builder
WORKDIR /app
COPY . .
RUN mkdir -p /app/dist && cp -r src/. /app/dist/

# --- STAGE 2 : Final ---
FROM nginx:alpine
RUN rm -rf /usr/share/nginx/html/*
COPY --from=builder /app/dist /usr/share/nginx/html

# Config Nginx ultra-standard
RUN echo 'server { listen 80; server_name localhost; root /usr/share/nginx/html; index index.html; location / { try_files $uri $uri/ /index.html; } }' > /etc/nginx/conf.d/default.conf

EXPOSE 80

# HEALTHCHECK : On utilise 127.0.0.1 au lieu de localhost pour éviter les bugs DNS
# On donne une marge de 30s pour être SÛR que Nginx a démarré
HEALTHCHECK --interval=10s --timeout=5s --retries=3 --start-period=30s \
  CMD wget -qO- http://127.0.0.1/ || exit 1