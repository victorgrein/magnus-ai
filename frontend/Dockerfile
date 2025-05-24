# Build stage
FROM node:20.15.1-alpine AS builder

WORKDIR /app

# Define build arguments with default values
ARG NEXT_PUBLIC_API_URL=https://api-evoai.evoapicloud.com

# Instalar pnpm globalmente
RUN npm install -g pnpm

# Install dependencies first (caching)
COPY package.json pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile

# Instalar explicitamente o next-runtime-env
RUN pnpm add next-runtime-env

# Copy source code
COPY . .

# Set environment variables from build arguments
ENV NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL}

RUN pnpm run build

# Production stage
FROM node:20.15.1-alpine AS runner

WORKDIR /app

# Define build arguments again for the runner stage
ARG NEXT_PUBLIC_API_URL=https://api-evoai.evoapicloud.com

# Instalar pnpm globalmente
RUN npm install -g pnpm

# Install production dependencies only
COPY package.json pnpm-lock.yaml ./
RUN pnpm install --prod --frozen-lockfile

# Instalar explicitamente o next-runtime-env na produção
RUN pnpm add next-runtime-env

# Copy built assets from builder
COPY --from=builder /app/.next ./.next
COPY --from=builder /app/public ./public
COPY --from=builder /app/next.config.mjs ./

# Set environment variables
ENV NODE_ENV=production
ENV PORT=3000
ENV NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL}

# Script to replace environment variables at runtime - create it diretamente no container
COPY docker-entrypoint.sh ./
RUN chmod +x ./docker-entrypoint.sh

# Expose port
EXPOSE 3000

# Use entrypoint script to initialize environment variables before starting the app
ENTRYPOINT ["sh", "./docker-entrypoint.sh"] 