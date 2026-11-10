#!/bin/sh
# Build the public app in Google Cloud and deploy it to Cloud Run (project clocked-london, Belgium).
# Uses the Google Cloud CLI in .tools (git-ignored). The API key comes from Secret Manager
# (secret "anthropic-api-key"); it is never read from or written to this repository.
# Run from anywhere:  sh ~/Desktop/App/scripts/deploy.sh
set -e
cd "$(dirname "$0")/.."
export CLOUDSDK_PYTHON="${CLOUDSDK_PYTHON:-/Library/Frameworks/Python.framework/Versions/3.11/bin/python3}"
exec .tools/google-cloud-sdk/bin/gcloud run deploy clocked --source . \
  --project clocked-london --region europe-west1 --allow-unauthenticated \
  --max-instances 1 --min-instances 0 --memory 512Mi --cpu 1 --timeout 60 --concurrency 4 \
  --set-secrets ANTHROPIC_API_KEY=anthropic-api-key:latest \
  --set-env-vars CLOCKED_FIELD_LOG=1
