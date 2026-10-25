
FROM node:20-slim AS builder

# Set working directory for the frontend build environment
WORKDIR /app

# Copy package manifests first to leverage Docker layer caching for npm packages
COPY package.json package-lock.json ./

# Install exact dependencies without running arbitrary scripts
RUN npm ci

# Copy the remaining frontend source code into the build container
COPY . .

# Compile and optimize production assets into the /app/dist directory
RUN npm run build

# ==============================================================================
# Stage 2: Production Nginx Server
# Uses ultra-lightweight nginx:alpine to serve compiled static files.
# No Node.js runtime or node_modules are included in this final production image.
# ==============================================================================
FROM nginx:alpine

# Remove default boilerplate configuration
RUN rm -rf /etc/nginx/conf.d/default.conf

# Copy custom Nginx configuration supporting React Router SPA fallback & gzip
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Copy compiled production bundle from Stage 1 into Nginx default document root
COPY --from=builder /app/dist /usr/share/nginx/html

# Expose port 80 for HTTP web traffic
EXPOSE 80

# Run Nginx in foreground daemon mode
CMD ["nginx", "-g", "daemon off;"]
