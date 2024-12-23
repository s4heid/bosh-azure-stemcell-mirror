# bosh-azure-stemcell-mirror

This repository contains an Azure Function that mirrors BOSH stemcells from [bosh.io](https://bosh.io/stemcells) to an [Azure Compute Gallery](https://learn.microsoft.com/en-us/azure/virtual-machines/azure-compute-gallery) of your choice.

## Prerequisites

- An Azure subscription
- An Azure service principal with the following permissions:
  - `Storage Blob Data Contributor` on the storage account
  - `Gallery Image Contributor` on the gallery
  - `Contributor` on the resource group

## Development

### Run the unit tests

```bash
python -m unittest discover tests
```

### Run the function locally

1. Install the [Azure Functions Core Tools](https://docs.microsoft.com/en-us/azure/azure-functions/functions-run-local?tabs=windows%2Ccsharp%2Cbash) and Azurite.

1. Configure a Python virtual environment using `venv` or your tool of choice.

    ```bash
    python -m venv .venv
    source ./.venv/bin/activate
    ```

1. Install the required Python packages:

    ```bash
    python -m pip install -r requirements.txt
    ```

1. Fill in the required environment variables in the `local.settings.json` file:

    ```json
    {
      "IsEncrypted": false,
      "Values": {
        "AzureWebJobsStorage": "UseDevelopmentStorage=true",
        "FUNCTIONS_WORKER_RUNTIME": "python",
        "BASM_AZURE_SUBSCRIPTION_ID": "yoursubscriptionid",
        "BASM_AZURE_TENANT_ID": "yourtenantid",
        "BASM_AZURE_CLIENT_ID": "yourclientid",
        "BASM_AZURE_CLIENT_SECRET": "yourclientsecret",
        "BASM_RESOURCE_GROUP": "yourresourcegroup",
        "BASM_STORAGE_ACCOUNT_NAME": "yoursstorageaccount",
        "BASM_STORAGE_CONTAINER_NAME": "yourcontainer",
        "BASM_MOUNTED_DIRECTORY": "/tmp",
        "BASM_GALLERY_NAME": "yourgallery"
      }
    }
    ```

1. Start the Azurite emulator in VS Code:

    ```console
    > Azurite start
    ```

1. Start the Azure Functions host:

    ```console
    > func host start
    ```

  Add `--verbose` flag to see detailed logs.

## Related Topics

- [Deploying BOSH Stemcells from Azure Compute Gallery](docs/deploying-bosh-stemcells-from-azure-compute-gallery.md)
- [Mirror BOSH stemcells using metalinks](https://github.com/dpb587/upstream-blob-mirror/blob/master/repository/bosh.io/stemcell/_metalink)
