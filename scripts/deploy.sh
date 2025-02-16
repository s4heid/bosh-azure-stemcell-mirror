#!/bin/bash

set -euox pipefail

if ! command -v azd &> /dev/null; then
    echo "Error: 'azd' command is not found. Please ensure you have 'azd' installed. For installation instructions, visit: https://learn.microsoft.com/en-us/azure/developer/azure-developer-cli/install-azd"
    exit 1
fi

if ! command -v az &> /dev/null; then
    echo "Error: 'az' command is not found. Please ensure you have 'az' installed. For installation instructions, visit: https://docs.microsoft.com/en-us/cli/azure/install-azure-cli"
    exit 1
fi

if ! command -v docker &> /dev/null; then
    echo "Error: 'docker' command is not found. Please ensure you have 'docker' installed. For installation instructions, visit: https://docs.docker.com/get-docker/"
    exit 1
fi

echo ""
echo "Loading azd .env file from current environment"
echo ""

while IFS='=' read -r key value; do
    if [[ $key =~ ^[^#]*$ ]]; then
        value="${value%\"}"
        value="${value#\"}"
        export "$key"="$value"
    fi
done < <(azd env get-values)

echo "Successfully loaded env vars from .env file."
: ${AZURE_TENANT_ID:?"Error: Missing AZURE_TENANT_ID in .env file"}
: ${AZURE_RESOURCE_GROUP:?"Error: Missing AZURE_RESOURCE_GROUP in .env file"}
: ${AZURE_CONTAINER_APPS_JOB_NAME:?"Error: Missing AZURE_CONTAINER_APPS_JOB_NAME in .env file"}
: ${AZURE_CONTAINER_REGISTRY_ENDPOINT:?"Error: Missing AZURE_CONTAINER_REGISTRY_ENDPOINT in .env file"}

if [[ "${AZD_IS_PROVISIONED:-false}" != "true" ]]; then
    echo "Azure resources are not provisioned. Please run 'azd provision' to set up the necessary resources before running this script."
    exit 1
fi

tag="azd-deploy-$(date +%Y%m%d%H%M%S)"
image="${AZURE_CONTAINER_REGISTRY_ENDPOINT}/bosh-azure-stemcell-mirror:$tag"

echo "Building Docker image..."
project_dir=$(realpath "$(dirname "$0")/..")
docker buildx build --platform linux/amd64 --build-arg arch=amd64 -t "$image" "$project_dir"

echo "Logging into Azure Container Registry..."
az acr login --name "$AZURE_CONTAINER_REGISTRY_ENDPOINT"

echo "Pushing Docker image ..."
docker push "$image"

echo "Updating Azure Container App Job..."
az containerapp job update --name "$AZURE_CONTAINER_APPS_JOB_NAME" --resource-group "${AZURE_RESOURCE_GROUP}" --image "$image"

echo
echo "Deployed Azure Container App Job successfully."
