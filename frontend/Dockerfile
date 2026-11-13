# The web image: Caddy serving the built app and forwarding /api to the API.
# Railway builds it with frontend/ as the root directory.

FROM node:24-slim AS build
WORKDIR /app
# Dependencies first, so a code change reuses this layer
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM caddy:2-alpine
COPY Caddyfile /etc/caddy/Caddyfile
COPY --from=build /app/dist /srv
