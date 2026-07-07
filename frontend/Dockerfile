FROM node:20-alpine AS build
WORKDIR /app

# Use the public npm registry and install from package.json only.
# This avoids stale lockfiles or bundled node_modules causing "vite: not found" / exit 127.
COPY package.json ./
RUN npm config set registry https://registry.npmjs.org/ \
    && npm install --no-audit --no-fund \
    && test -x ./node_modules/.bin/vite \
    && ./node_modules/.bin/vite --version

COPY index.html ./
COPY src ./src
RUN ./node_modules/.bin/vite build

FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
