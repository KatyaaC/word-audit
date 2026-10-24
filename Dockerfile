# Hugging Face Space (Docker SDK). Serves the Next.js app on port 7860 in demo-data mode.
FROM node:20-slim AS build
WORKDIR /app
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web/ ./
ENV NEXT_TELEMETRY_DISABLED=1 NEXT_PUBLIC_USE_MOCKS=true
RUN npm run build

FROM node:20-slim
WORKDIR /app
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1 PORT=7860 HOSTNAME=0.0.0.0
COPY --from=build /app ./
RUN chown -R 1000:1000 /app
USER 1000
EXPOSE 7860
CMD ["npx", "next", "start", "-p", "7860", "-H", "0.0.0.0"]
