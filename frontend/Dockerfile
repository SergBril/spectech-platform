# ============================================
# Multi-stage Dockerfile for Frontend (Vite 5)
# ============================================

FROM node:20-alpine AS builder

WORKDIR /app

# ARG для Vite переменных (запекаются в JS на этапе build)
ARG VITE_API_URL=http://localhost:8080/api/v1
ARG VITE_WS_URL=ws://localhost:8080/api/v1/ws

ENV VITE_API_URL=$VITE_API_URL
ENV VITE_WS_URL=$VITE_WS_URL
ENV NODE_OPTIONS="--max-old-space-size=4096"

# Копируем package файлы
COPY package*.json ./

# Удаляем package-lock.json чтобы форсировать свежие установки
RUN rm -f package-lock.json

# Устанавливаем зависимости (без lock файла)
RUN npm install --no-fund --no-audit

# Копируем исходники
COPY . .

# Билдим production версию
RUN npm run build

# Stage 2: Serve with Nginx
FROM nginx:alpine

RUN rm /etc/nginx/conf.d/default.conf

COPY nginx.conf /etc/nginx/conf.d/default.conf

# Копируем собранные файлы
COPY --from=builder /app/dist /usr/share/nginx/html

EXPOSE 3000

HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD wget --quiet --tries=1 --spider http://localhost:3000/ || exit 1

CMD ["nginx", "-g", "daemon off;"]
