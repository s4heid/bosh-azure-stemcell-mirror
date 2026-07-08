import logging
import os
import uuid

from azure.core.exceptions import HttpResponseError, ResourceNotFoundError
from azure.identity import AzureAuthorityHosts, DefaultAzureCredential
from azure.mgmt.compute import ComputeManagementClient
from azure.mgmt.compute.models import (
    GalleryDiskImageSource,
    GalleryImage,
    GalleryImageFeature,
    GalleryImageIdentifier,
    GalleryImageVersion,
    GalleryImageVersionProperties,
    GalleryImageVersionPublishingProfile,
    GalleryImageVersionStorageProfile,
    GalleryOSDiskImage,
    TargetRegion,
)
from azure.storage.blob import BlobServiceClient, ContainerClient

DEFAULT_GENERATION = "gen1"


def _hyper_v_generation(generation: str) -> str:
    return f"V{generation.lower().removeprefix('gen')}"


def _normalize_architecture(architecture: str | None) -> str | None:
    if not architecture:
        return None
    normalized = architecture.lower()
    if normalized in ("x86_64", "x64"):
        return "x64"
    if normalized == "arm64":
        return "Arm64"
    return architecture


def _normalize_disk_controllers(disk_controllers: list) -> list:
    normalized = []
    for controller in disk_controllers:
        value = str(controller).lower()
        if value == "scsi":
            normalized.append("SCSI")
        elif value == "nvme":
            normalized.append("NVMe")
        else:
            normalized.append(controller)
    return normalized


class AzureManager:
    def __init__(
        self,
        subscription_id: str,
        client_id: str,
        resource_group: str,
        location: str,
        logger: logging.Logger | None = None,
    ) -> None:
        self.subscription_id: str = subscription_id
        self.resource_group: str = resource_group
        self.location: str = location
        self.credential: DefaultAzureCredential = DefaultAzureCredential(
            managed_identity_client_id=client_id, authority=AzureAuthorityHosts.AZURE_PUBLIC_CLOUD
        )
        self.compute_client: ComputeManagementClient = ComputeManagementClient(self.credential, subscription_id)
        self.container_client: ContainerClient | None = None
        self.storage_account_name: str | None = None
        self.storage_container: str | None = None
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

    def check_or_create_gallery_image(
        self,
        stemcell_series: str,
        gallery_name: str,
        gallery_image_name: str,
        cloud_properties: dict | None = None,
    ) -> None:
        cloud_properties = cloud_properties or {}
        try:
            self.compute_client.gallery_images.get(self.resource_group, gallery_name, gallery_image_name)
            self.logger.info("Gallery image definition already exists.")
        except ResourceNotFoundError:
            self.logger.info("Creating new gallery image definition...")
            generation: str = str(cloud_properties.get("generation", DEFAULT_GENERATION))
            gallery_image_params: GalleryImage = GalleryImage(  # pyright: ignore[reportCallIssue]
                location=self.location,
                identifier=GalleryImageIdentifier(
                    publisher=os.environ.get("BASM_GALLERY_PUBLISHER", "bosh"),
                    offer=os.environ.get("BASM_GALLERY_OFFER", stemcell_series),
                    sku=os.environ.get("BASM_GALLERY_SKU", generation),
                ),
                os_type="Linux",
                os_state="Generalized",
                hyper_v_generation=_hyper_v_generation(generation),
                architecture=_normalize_architecture(cloud_properties.get("architecture")),
                features=self._build_gallery_image_features(cloud_properties) or None,
            )
            self.compute_client.gallery_images.begin_create_or_update(
                resource_group_name=self.resource_group,
                gallery_name=gallery_name,
                gallery_image_name=gallery_image_name,
                gallery_image=gallery_image_params,
            )
            self.logger.info("Gallery image definition created.")

    def _build_gallery_image_features(self, cloud_properties: dict) -> list[GalleryImageFeature]:
        """Build gallery image features from stemcell cloud properties.

        Features only apply to generation 2 images, mirroring the bosh-azure-cpi.
        """
        generation: str = str(cloud_properties.get("generation", DEFAULT_GENERATION)).lower()
        if generation == DEFAULT_GENERATION:
            return []

        features: list[GalleryImageFeature] = []

        if "disk_controller_types" in cloud_properties:
            disk_controllers = cloud_properties["disk_controller_types"]
            if isinstance(disk_controllers, list) and disk_controllers:
                features.append(
                    GalleryImageFeature(
                        name="DiskControllerTypes",
                        value=",".join(_normalize_disk_controllers(disk_controllers)),
                    )
                )
            else:
                self.logger.warning(f"Ignoring invalid 'disk_controller_types' metadata: {disk_controllers}")

        if "accelerated_networking" in cloud_properties:
            features.append(
                GalleryImageFeature(
                    name="IsAcceleratedNetworkSupported",
                    value="True" if cloud_properties["accelerated_networking"] else "False",
                )
            )

        if "hibernation" in cloud_properties:
            features.append(
                GalleryImageFeature(
                    name="IsHibernateSupported",
                    value="True" if cloud_properties["hibernation"] else "False",
                )
            )

        if "security_type" in cloud_properties:
            features.append(
                GalleryImageFeature(
                    name="SecurityType",
                    value=cloud_properties["security_type"],
                )
            )

        return features

    def create_gallery_image_version(
        self, gallery_name: str, gallery_image_name: str, gallery_image_version: str, blob_uri: str
    ) -> None:
        storage_account_id = (
            f"/subscriptions/{self.subscription_id}/resourceGroups/{self.resource_group}"
            f"/providers/Microsoft.Storage/storageAccounts/{self.storage_account_name}"
        )
        image_version = GalleryImageVersion(
            location=self.location,
            properties=GalleryImageVersionProperties(
                publishing_profile=GalleryImageVersionPublishingProfile(
                    target_regions=[TargetRegion(name=self.location, regional_replica_count=1)],
                ),
                storage_profile=GalleryImageVersionStorageProfile(
                    os_disk_image=GalleryOSDiskImage(
                        source=GalleryDiskImageSource(
                            storage_account_id=storage_account_id,
                            uri=blob_uri,
                        ),
                    ),
                ),
            ),
        )
        self.compute_client.gallery_image_versions.begin_create_or_update(
            self.resource_group,
            gallery_name,
            gallery_image_name,
            gallery_image_version,
            image_version,
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
