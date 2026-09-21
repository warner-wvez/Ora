FROM node:20-alpine
WORKDIR /app
COPY relay.js server.js ./
ENV PORT=8791
EXPOSE 8791
USER node
HEALTHCHECK --interval=60s --timeout=10s --retries=3 CMD wget -qO- http://127.0.0.1:8791/healthz || exit 1
CMD ["node", "server.js"]
