# bosh-azure-stemcell-mirror

This repository contains an Azure Function that mirrors BOSH stemcells from [bosh.io](https://bosh.io/stemcells) to an [Azure Compute Gallery](https://learn.microsoft.com/en-us/azure/virtual-machines/azure-compute-gallery) of your choice.

## Prerequisites

- An Azure subscription
- An Azure service principal with the following permissions:
  - `Storage Blob Data Contributor` on the storage account
  - `Gallery Image Contributor` on the gallery
  - `Contributor` on the resource group

## Deployment

First, log-in to your Azure subscription using `azd auth login`. Run `azd up` to provision your infrastructure and deploy to Azure (or run `azd provision` then `azd deploy` to accomplish the tasks separately).

## Development

1. Install the `Azure Container Apps` VS Code Extension.

2. Configure a Python virtual environment using `venv` or your tool of choice.

    ```bash
    python -m venv .venv
    source ./.venv/bin/activate
    ```

3. Install the required Python packages:

    ```bash
    python -m pip install -r requirements.txt
    ```

4. Run the unit tests:

    ```bash
    python -m unittest discover tests
    ```

## Related Topics

- [Deploying BOSH Stemcells from Azure Compute Gallery](docs/deploying-bosh-stemcells-from-azure-compute-gallery.md)
- [Mirror BOSH stemcells using metalinks](https://github.com/dpb587/upstream-blob-mirror/blob/master/repository/bosh.io/stemcell/_metalink)
