FROM node:20-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:1.27-alpine
COPY nginx.conf.template /etc/nginx/templates/default.conf.template
COPY --from=build /app/dist /usr/share/nginx/html
ENV PORT=8080
# Restrict envsubst templating to API_URL only — by default it substitutes
# every env var, which clobbers nginx's own $host/$scheme/$uri etc. in the
# template since they share the same ${VAR} syntax.
ENV NGINX_ENVSUBST_FILTER=^API_URL$
EXPOSE 8080
