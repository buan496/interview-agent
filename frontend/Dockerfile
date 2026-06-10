FROM node:20-alpine AS deps

WORKDIR /app/frontend
COPY frontend/package.json ./
RUN npm install

FROM node:20-alpine AS builder

WORKDIR /app/frontend
ARG NEXT_PUBLIC_API_BASE_URL=http://localhost:8000/api
ENV NEXT_PUBLIC_API_BASE_URL=$NEXT_PUBLIC_API_BASE_URL
COPY --from=deps /app/frontend/node_modules ./node_modules
COPY frontend .
RUN npm run build

FROM node:20-alpine AS runner

WORKDIR /app/frontend
ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1
COPY --from=builder /app/frontend/.next ./.next
COPY --from=builder /app/frontend/public ./public
COPY --from=builder /app/frontend/package.json ./package.json
COPY --from=builder /app/frontend/node_modules ./node_modules

EXPOSE 3000
CMD ["npm", "run", "start", "--", "-p", "3000"]

