import os
import uuid
import logging

from azure.core.exceptions import ResourceNotFoundError, HttpResponseError
from azure.mgmt.compute import ComputeManagementClient
from azure.mgmt.compute.models import GalleryImage, GalleryImageIdentifier
from azure.storage.blob import BlobServiceClient, ContainerClient
from azure.identity import DefaultAzureCredential, AzureAuthorityHosts
from typing import Optional


class AzureManager:
    def __init__(
        self,
        subscription_id: str,
        client_id: str,
        resource_group: str,
        location: str,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        self.subscription_id: str = subscription_id
        self.resource_group: str = resource_group
        self.location: str = location
        self.credential: DefaultAzureCredential = DefaultAzureCredential(
            managed_identity_client_id=client_id, authority=AzureAuthorityHosts.AZURE_PUBLIC_CLOUD
        )
        self.compute_client: ComputeManagementClient = ComputeManagementClient(self.credential, subscription_id)
        self.container_client: Optional[ContainerClient] = None
        self.storage_account_name: Optional[str] = None
        self.storage_container: Optional[str] = None
        self.logger: logging.Logger = logger or logging.getLogger(__name__)

    def setup_storage(self, storage_account_name: str, storage_container: str) -> None:
        self.storage_account_name = storage_account_name
        self.storage_container = storage_container
        blob_service_client: BlobServiceClient = BlobServiceClient(
            f"https://{storage_account_name}.blob.core.windows.net",
            self.credential,
            max_block_size=1024 * 1024 * 64,  # 64 MiB
            max_single_put_size=1024 * 1024 * 256,  # 256 MiB
        )
        self.container_client = blob_service_client.get_container_client(storage_container)
        if not self.container_client.exists():
            self.container_client.create_container()

    def upload_vhd(self, vhd_path: str) -> str:
        if not self.container_client:
            raise ValueError("Storage account not configured.")

        blob_name: str = f"bosh-stemcell-{uuid.uuid4()}.vhd"
        try:
            with open(vhd_path, "rb") as data:
                self.container_client.upload_blob(
                    name=blob_name, data=data, blob_type="PageBlob", overwrite=True, max_concurrency=4
                )
            self.logger.info(f"Uploaded VHD to blob: {blob_name}")
        except HttpResponseError as e:
            self.logger.error(f"Failed to upload VHD: {e.message}")
            raise e
        except Exception as e:
            self.logger.error(f"An unexpected error occurred during VHD upload: {str(e)}")
            raise e

        return f"https://{self.storage_account_name}.blob.core.windows.net/{self.storage_container}/{blob_name}"

    def check_or_create_gallery_image(self, stemcell_series: str, gallery_name: str, gallery_image_name: str) -> None:
        try:
            self.compute_client.gallery_images.get(self.resource_group, gallery_name, gallery_image_name)
            self.logger.info("Gallery image definition already exists.")
        except ResourceNotFoundError:
            self.logger.info("Creating new gallery image definition...")
            gallery_image_params: GalleryImage = GalleryImage(
                location=self.location,
                identifier=GalleryImageIdentifier(
                    publisher=os.environ.get("BASM_GALLERY_PUBLISHER", "bosh"),
                    offer=os.environ.get("BASM_GALLERY_OFFER", stemcell_series.split("-")[3]),
                    sku=os.environ.get("BASM_GALLERY_SKU", stemcell_series.split("-")[4]),
                ),
                os_type="Linux",
                hyper_v_generation="V1",
            )
            self.compute_client.gallery_images.begin_create_or_update(
                resource_group_name=self.resource_group,
                gallery_name=gallery_name,
                gallery_image_name=gallery_image_name,
                gallery_image=gallery_image_params,
            )
            self.logger.info("Gallery image definition created.")

    def create_gallery_image_version(
        self, gallery_name: str, gallery_image_name: str, gallery_image_version: str, blob_uri: str
    ) -> None:
        self.compute_client.gallery_image_versions.begin_create_or_update(
            self.resource_group,
            gallery_name,
            gallery_image_name,
            gallery_image_version,
            {
                "location": self.location,
                "publishingProfile": {"targetRegions": [{"name": self.location, "regionalReplicaCount": 1}]},
                "storageProfile": {
                    "osDiskImage": {
                        "source": {
                            "storageAccountId": f"/subscriptions/{self.subscription_id}/resourceGroups/{self.resource_group}/providers/Microsoft.Storage/storageAccounts/{self.storage_account_name}",
                            "uri": blob_uri,
                        }
                    }
                },
            },
        )
        self.logger.info(f"Gallery image version {gallery_image_version} creation initiated.")

    def gallery_image_version_exists(
        self, gallery_name: str, gallery_image_name: str, gallery_image_version: str
    ) -> bool:
        try:
            self.compute_client.gallery_image_versions.get(
                resource_group_name=self.resource_group,
                gallery_name=gallery_name,
                gallery_image_name=gallery_image_name,
                gallery_image_version_name=gallery_image_version,
            )
            return True
        except ResourceNotFoundError:
            return False
        except Exception as e:
            raise e
