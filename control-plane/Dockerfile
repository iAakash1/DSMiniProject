FROM node:22-slim AS build

ARG NEXT_PUBLIC_CONTROL_API_URL
ENV NEXT_PUBLIC_CONTROL_API_URL=$NEXT_PUBLIC_CONTROL_API_URL

WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm install

COPY . .
RUN npm run build

FROM node:22-slim

ENV NODE_ENV=production

WORKDIR /app

COPY --from=build /app/.next ./.next
COPY --from=build /app/public ./public
COPY --from=build /app/package.json ./package.json
COPY --from=build /app/node_modules ./node_modules

EXPOSE 3100

CMD ["npm", "run", "start"]
