# The public Clocked server for Cloud Run: the web app built without test mode,
# served by the recognition server on the same address.

# 1. Build the public web app (npm run build also checks it contains no test mode).
FROM node:20-slim AS web
WORKDIR /app/web
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web/ ./
RUN npm run build

# 2. The server.
FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY server/requirements.txt server/requirements.txt
RUN pip install --no-cache-dir -r server/requirements.txt
COPY server/clocked server/clocked
COPY data/london_collection_v4.csv data/london_collection_v4.csv
COPY --from=web /app/web/dist web/dist

# The cost ledger lives in the container's memory-backed disk and starts empty on
# each new instance; the real spending limit is the prepaid credit in the Console.
ENV CLOCKED_COST_LEDGER=/tmp/cost_ledger.csv
# Cloud Run sets PORT. Development mode and test mode stay off.
CMD exec uvicorn clocked.app:create_app --factory --app-dir server --host 0.0.0.0 --port ${PORT:-8080}
