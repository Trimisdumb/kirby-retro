# Aucune dépendance npm : le serveur n'utilise que node:http / node:fs / node:sqlite.
FROM node:22-alpine

ENV NODE_ENV=production \
    PORT=8090 \
    NODE_OPTIONS=--disable-warning=ExperimentalWarning

WORKDIR /app

COPY package.json ./
COPY src ./src
COPY public ./public
COPY scripts ./scripts

RUN mkdir -p /data/roms /data/ejs /data/covers /data/state \
    && chown -R node:node /data

USER node
EXPOSE 8090

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD node -e "fetch('http://127.0.0.1:'+(process.env.PORT||8090)+'/healthz').then(r=>process.exit(r.ok?0:1)).catch(()=>process.exit(1))"

CMD ["node", "src/server.mjs"]
