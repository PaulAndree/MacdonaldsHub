FROM node:22-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY index.html tsconfig.json vite.config.ts ./
COPY src ./src
COPY scripts ./scripts
COPY public-example ./public-example
# EXAMPLE_MODE=true builds the example-data variant (design D1). It exists only for the test environment:
# the default is the standard build, and the check below fails the image if the bundle is not the variant asked for.
ARG EXAMPLE_MODE=false
RUN if [ "$EXAMPLE_MODE" = "true" ]; then variant=example; else variant=standard; fi \
    && if [ "$variant" = "example" ]; then npm run build:example; else npm run build; fi \
    && node scripts/check-bundle.mjs "$variant" dist

# Serves the SPA and proxies /api/* to the internal API. Listens on 3000.
FROM nginxinc/nginx-unprivileged:1.27-alpine
USER root
RUN mkdir -p /etc/nginx/identity && chown nginx:nginx /etc/nginx/identity
COPY nginx/default.conf.template /etc/nginx/templates/default.conf.template
COPY nginx/identity-forward.conf nginx/identity-strip.conf /etc/nginx/identity-available/
COPY nginx/40-identity-headers.sh /docker-entrypoint.d/40-identity-headers.sh
RUN chmod +x /docker-entrypoint.d/40-identity-headers.sh
COPY --from=build /app/dist /usr/share/nginx/html
USER nginx
ENV NGINX_ENVSUBST_FILTER=API_UPSTREAM TRUST_EASY_AUTH_HEADERS=false
EXPOSE 3000
HEALTHCHECK --interval=15s --timeout=3s --retries=3 CMD wget -q -O /dev/null http://127.0.0.1:3000/healthz || exit 1
