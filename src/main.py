import os
import sys
import logging

from mirror.azure_manager import AzureManager
from mirror.stemcell_mirror import StemcellMirror

subscription_id: str = os.environ["AZURE_SUBSCRIPTION_ID"]
managed_identity_client_id: str = os.environ.get("AZURE_CONTAINER_REGISTRY_MANAGED_IDENTITY_ID")
resource_group: str = os.environ["AZURE_RESOURCE_GROUP"]
location: str = os.environ.get("AZURE_REGION", "eastus")
storage_account_name: str = os.environ["BASM_STORAGE_ACCOUNT_NAME"]
gallery_name: str = os.environ.get("BASM_GALLERY_NAME", "bosh-azure-stemcells")
storage_container: str = os.environ.get("BASM_STORAGE_CONTAINER_NAME", "stemcell")
gallery_image_name: str = os.environ.get("BASM_GALLERY_IMAGE_NAME", "ubuntu-jammy")
stemcell_series: str = os.environ.get("BASM_STEMCELL_SERIES", "bosh-azure-hyperv-ubuntu-jammy-go_agent")
mounted_dir: str = os.environ.get("BASM_MOUNTED_DIRECTORY", "")

if __name__ == "__main__":
    app_logger: logging.Logger = logging.getLogger(__name__)
    app_logger.setLevel(logging.INFO)
    handler: logging.StreamHandler = logging.StreamHandler(stream=sys.stdout)
    app_logger.addHandler(handler)

    # Azure SDK logs are too verbose, so we'll suppress them.
    az_logger: logging.Logger = logging.getLogger("azure")
    az_logger.setLevel(logging.WARN)
    az_logger.addHandler(handler)

    app_logger.info("Setting up Azure Manager...")

    azure_manager: AzureManager = AzureManager(
        subscription_id=subscription_id,
        client_id=managed_identity_client_id,
        resource_group=resource_group,
        location=location,
        logger=app_logger,
    )
    azure_manager.setup_storage(storage_account_name, storage_container)

    app_logger.info("Starting stemcell mirror run...")

    mirror: StemcellMirror = StemcellMirror(azure_manager, mounted_dir, logger=app_logger)
    mirror.run(stemcell_series, gallery_name, gallery_image_name)

    app_logger.info("Completed stemcell mirror run.")
