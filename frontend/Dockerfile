FROM node:22-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:1.27-alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY deploy/spa.conf /etc/nginx/conf.d/default.conf
HEALTHCHECK --interval=15s --timeout=3s --retries=4 CMD wget -qO- http://localhost/ >/dev/null || exit 1
