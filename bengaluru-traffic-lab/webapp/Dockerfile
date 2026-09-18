# Build context is bengaluru-traffic-lab/ (the Railway service's root
# directory) so this can COPY both webapp/ and its sibling docs/ — a plain
# Nixpacks build scoped to webapp/ alone can't see docs/ at all, which is
# what crashed the first deploy attempt (ENOENT on docs/).
FROM node:18-slim
WORKDIR /app

COPY webapp/package.json webapp/
RUN cd webapp && npm install --omit=dev
COPY webapp/server.js webapp/
COPY docs docs/

ENV PORT=3000
EXPOSE 3000
WORKDIR /app/webapp
CMD ["node", "server.js"]
