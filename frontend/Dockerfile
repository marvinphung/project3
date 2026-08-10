FROM node:22-alpine AS build
WORKDIR /app
COPY frontend/package.json frontend/pnpm-lock.yaml ./
RUN corepack enable && corepack pnpm install --frozen-lockfile
COPY frontend/ ./
ENV VITE_API_BASE_URL=/api
ENV VITE_CRAWLER_API_BASE_URL=/crawler
RUN corepack pnpm build

FROM nginx:1.27-alpine
COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
HEALTHCHECK --interval=10s --timeout=3s --retries=10 CMD wget -qO- http://127.0.0.1/ >/dev/null || exit 1
