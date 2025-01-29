# bosh-azure-stemcell-mirror

[![Tests](https://github.com/s4heid/bosh-azure-stemcell-mirror/actions/workflows/test.yaml/badge.svg?branch=main)](https://github.com/s4heid/bosh-azure-stemcell-mirror/actions/workflows/test.yaml)
[![Open in Dev Containers](https://img.shields.io/static/v1?label=Dev%20Containers&message=Open&color=blue)](https://vscode.dev/redirect?url=vscode://ms-vscode-remote.remote-containers/cloneInVolume?url=https://github.com/s4heid/bosh-azure-stemcell-mirror)

This repository contains an Azure Function that mirrors BOSH stemcells from [bosh.io](https://bosh.io/stemcells) to an [Azure Compute Gallery](https://learn.microsoft.com/en-us/azure/virtual-machines/azure-compute-gallery) of your choice.

## Architecture

```mermaid
sequenceDiagram
    participant User
    participant StemcellMirror as StemcellMirror.run()
    participant BoshIO as bosh.io
    participant Storage as Azure Storage Account
    participant Gallery as Azure Compute Gallery

    User->>StemcellMirror: Invoke
    StemcellMirror->>Gallery: gallery_image_version_exists?
    alt VersionExists
        StemcellMirror->>User: No new stemcell required
    else NoVersionFound
        StemcellMirror->>BoshIO: Download latest stemcell (tgz)
        StemcellMirror->>StemcellMirror: Extract .vhd from tgz
        StemcellMirror->>Storage: Upload root.vhd
        StemcellMirror->>Gallery: check_or_create_gallery_image
        StemcellMirror->>Gallery: create_gallery_image_version
    end
    StemcellMirror->>User: Completed stemcell check
```

## Deployment

1. Get an Azure Subscription
2. Log-in to your Azure subscription using `azd auth login`.
3. Run `azd up` to provision your infrastructure and deploy to Azure (or run `azd provision` then `azd deploy` to accomplish the tasks separately).

## Development

1. Configure a Python virtual environment using `venv` or your tool of choice.

    ```bash
    python -m venv .venv
    source ./.venv/bin/activate
    ```

2. Install the required Python packages:

    ```bash
    python -m pip install -r requirements.txt
    ```

3. Run the unit tests:

    ```bash
    python -m unittest discover tests
    ```

## Related Topics

- [Deploying BOSH Stemcells from Azure Compute Gallery](docs/deploying-bosh-stemcells-from-azure-compute-gallery.md)
- [Mirror BOSH stemcells using metalinks](https://github.com/dpb587/upstream-blob-mirror/blob/master/repository/bosh.io/stemcell/_metalink)
