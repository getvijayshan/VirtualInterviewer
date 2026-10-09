#!/usr/bin/env bash
# Provisions the Blob storage account + container and the Azure AI Foundry
# resource/project (see ADR §4c/§4d). Mirrors infra/az-resource/Deployment-*.
# Like provision_vm.sh this is NOT idempotent — it creates everything and fails
# on existing resources. Requires `az login` (CI: azure/login).
#
# NOTE: the first hand-built account (virtualinterviewsa) was kind=FileStorage and
# cannot hold blobs; the replacement blobstoragevoicevi is StorageV2 and is mirrored here.
#
# Optional env vars (defaults match the hand-built environment):
#   STORAGE_RESOURCE_GROUP   resource-virtual-interviewer
#   STORAGE_LOCATION         centralindia
#   STORAGE_ACCOUNT          blobstoragevoicevi
#   STORAGE_CONTAINER        resume-answer-audio
#   AI_RESOURCE_GROUP        southindia-ai-models
#   AI_LOCATION              southindia  (Central India doesn't offer these models)
#   AI_FOUNDRY_NAME          ai-foundry-southindia
#   AI_PROJECT_NAME          ai-resource-south-india

set -euo pipefail

STORAGE_RESOURCE_GROUP="${STORAGE_RESOURCE_GROUP:-resource-virtual-interviewer}"
STORAGE_LOCATION="${STORAGE_LOCATION:-centralindia}"
STORAGE_ACCOUNT="${STORAGE_ACCOUNT:-blobstoragevoicevi}"
STORAGE_CONTAINER="${STORAGE_CONTAINER:-resume-answer-audio}"
AI_RESOURCE_GROUP="${AI_RESOURCE_GROUP:-southindia-ai-models}"
AI_LOCATION="${AI_LOCATION:-southindia}"
AI_FOUNDRY_NAME="${AI_FOUNDRY_NAME:-ai-foundry-southindia}"
AI_PROJECT_NAME="${AI_PROJECT_NAME:-ai-resource-south-india}"

SUBSCRIPTION_ID=$(az account show --query id --output tsv)

echo "== Storage account: ${STORAGE_ACCOUNT} (StorageV2, Standard_LRS) =="
az group create --name "$STORAGE_RESOURCE_GROUP" --location "$STORAGE_LOCATION" --output none
az storage account create \
  --resource-group "$STORAGE_RESOURCE_GROUP" --name "$STORAGE_ACCOUNT" --location "$STORAGE_LOCATION" \
  --kind StorageV2 --sku Standard_LRS --access-tier Hot \
  --min-tls-version TLS1_2 --https-only true \
  --allow-blob-public-access false --allow-shared-key-access true \
  --output none
az storage account blob-service-properties update \
  --resource-group "$STORAGE_RESOURCE_GROUP" --account-name "$STORAGE_ACCOUNT" \
  --enable-delete-retention true --delete-retention-days 7 \
  --enable-container-delete-retention true --container-delete-retention-days 7 --output none
az storage container create \
  --account-name "$STORAGE_ACCOUNT" --name "$STORAGE_CONTAINER" \
  --auth-mode key --public-access off --output none

echo "== AI Foundry: ${AI_FOUNDRY_NAME} (${AI_LOCATION}) =="
az group create --name "$AI_RESOURCE_GROUP" --location "$AI_LOCATION" --output none
az cognitiveservices account create \
  --resource-group "$AI_RESOURCE_GROUP" --name "$AI_FOUNDRY_NAME" --location "$AI_LOCATION" \
  --kind AIServices --sku S0 --custom-domain "$AI_FOUNDRY_NAME" \
  --assign-identity --yes --output none
# Enable Foundry project management on the account, then create the project.
FOUNDRY_ID="/subscriptions/${SUBSCRIPTION_ID}/resourceGroups/${AI_RESOURCE_GROUP}/providers/Microsoft.CognitiveServices/accounts/${AI_FOUNDRY_NAME}"
az rest --method patch \
  --url "https://management.azure.com${FOUNDRY_ID}?api-version=2025-06-01" \
  --body '{"properties":{"allowProjectManagement":true}}' --output none
az rest --method put \
  --url "https://management.azure.com${FOUNDRY_ID}/projects/${AI_PROJECT_NAME}?api-version=2025-06-01" \
  --body "{\"location\":\"${AI_LOCATION}\",\"identity\":{\"type\":\"SystemAssigned\"},\"properties\":{}}" \
  --output none

echo "Done. Model deployments (e.g. gpt-5-mini) are not created here."
