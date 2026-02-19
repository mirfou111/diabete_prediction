# --- STAGE 1 : Build ---
FROM alpine:latest AS builder
WORKDIR /app
COPY . .
RUN mkdir -p /app/dist && cp -r src/. /app/dist/

# --- STAGE 2 : Final ---
FROM nginx:alpine
RUN rm -rf /usr/share/nginx/html/*
COPY --from=builder /app/dist /usr/share/nginx/html

# Configuration Nginx avec le REVERSE PROXY vers le Backend
# On redirige /api/ vers le service "web" défini dans Docker Swarm / Compose
RUN echo 'server { \
    listen 80; \
    root /usr/share/nginx/html; \
    index index.html; \
    location / { \
        try_files $uri $uri/ /index.html; \
    } \
    location /api/ { \
        proxy_pass http://web:5000/; \
        proxy_set_header Host $host; \
        proxy_set_header X-Real-IP $remote_addr; \
    } \
}' > /etc/nginx/conf.d/default.conf

EXPOSE 80

HEALTHCHECK --interval=10s --timeout=5s --retries=3 --start-period=30s \
  CMD wget -qO- http://127.0.0.1/ || exit 1
