# Builds one Next.js app (storefront or staff) as a standalone server. Usage: --build-arg APP=storefront
ARG NODE_IMAGE=node:22-alpine

FROM ${NODE_IMAGE} AS build
ARG APP
RUN corepack enable
WORKDIR /repo
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml .npmrc ./
COPY packages ./packages
COPY e2e/package.json ./e2e/package.json
COPY apps/${APP} ./apps/${APP}
# Generous retries and timeouts so slow or unstable connections finish instead of failing.
ENV npm_config_fetch_retries=10 \
    npm_config_fetch_retry_maxtimeout=120000 \
    npm_config_fetch_timeout=300000
RUN pnpm install --frozen-lockfile --filter "@aurevon/${APP}..."
ENV NEXT_TELEMETRY_DISABLED=1
RUN pnpm --filter "@aurevon/${APP}" build

FROM ${NODE_IMAGE} AS run
ARG APP
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    HOSTNAME=0.0.0.0 \
    APP=${APP}
WORKDIR /app
RUN addgroup -S app && adduser -S app -G app
COPY --from=build --chown=app:app /repo/apps/${APP}/.next/standalone ./
COPY --from=build --chown=app:app /repo/apps/${APP}/.next/static ./apps/${APP}/.next/static
# Static files (the 3D viewer's Draco decoder, copied at build time).
COPY --from=build --chown=app:app /repo/apps/${APP}/public ./apps/${APP}/public
USER app
CMD ["sh", "-c", "node apps/${APP}/server.js"]
