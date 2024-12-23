import unittest
from unittest.mock import MagicMock, patch, mock_open
import unittest.mock
from azure.core.exceptions import ResourceNotFoundError
from azure.storage.blob import BlobServiceClient, ContainerClient
from azure.mgmt.compute.models import GalleryImageVersion
from mirror.azure_manager import AzureManager
from azure.mgmt.compute import ComputeManagementClient

class TestAzureManager(unittest.TestCase):
    @patch("mirror.azure_manager.ClientSecretCredential")
    @patch("mirror.azure_manager.ComputeManagementClient")
    def setUp(self, mock_compute_client, mock_credential) -> None:
        self.mock_logger = MagicMock()
        self.manager = AzureManager(
            client_id="test-client-id",
            client_secret="test-client-secret",
            tenant_id="test-tenant-id",
            subscription_id="test-subscription-id",
            resource_group="test-rg",
            location="test-location",
            logger=self.mock_logger
        )
        self.mock_compute_client = mock_compute_client

    @patch("mirror.azure_manager.BlobServiceClient")
    def test_setup_storage(self, mock_blob_service_client: BlobServiceClient) -> None:
        mock_container_client: ContainerClient = make_mock_container_client(mock_blob_service_client, exists=False)

        self.manager.setup_storage("teststorage123", "testcontainer123")

        self.assertEqual(self.manager.storage_account_name, "teststorage123")
        self.assertEqual(self.manager.storage_container, "testcontainer123")
        mock_container_client.create_container.assert_called_once()

    @patch("mirror.azure_manager.BlobServiceClient")
    def test_upload_vhd(self, mock_blob_service_client: BlobServiceClient) -> None:
        mock_container_client: ContainerClient = make_mock_container_client(mock_blob_service_client)
        self.manager.setup_storage("teststorage", "testcontainer")

        with patch("builtins.open", mock_open(read_data=b"fake-vhd")):
            url = self.manager.upload_vhd("fake.vhd")

        self.assertIn("https://teststorage.blob.core.windows.net/testcontainer/bosh-stemcell-", url)
        self.assertIn(".vhd", url)
        mock_container_client.upload_blob.assert_called_once_with(
            name=unittest.mock.ANY,
            data=unittest.mock.ANY,
            overwrite=True,
            blob_type="PageBlob",
            max_concurrency=unittest.mock.ANY
        )
        self.assertTrue(
            any(call.args[0].startswith("Uploaded VHD to blob: bosh-stemcell-") for call in self.mock_logger.info.mock_calls),
            "Expected log message starting with 'Uploaded VHD to blob: '"
        )

    def test_upload_vhd_no_storage_config_raises(self):
        with self.assertRaises(ValueError):
            self.manager.upload_vhd("fake.vhd")

    def test_check_or_create_gallery_image_exists(self):
        self.mock_compute_client.return_value.gallery_images.get.return_value = GalleryImageVersion(
            id="test",
            location="test",
            tags={},
            os_type="test",
            os_state="test",
            publishing_profile=None
        )

        self.manager.check_or_create_gallery_image("series", "gallery", "img")

        self.mock_logger.info.assert_any_call("Gallery image definition already exists.")
        self.mock_compute_client.return_value.gallery_images.begin_create_or_update.assert_not_called()

    def test_check_or_create_gallery_image_not_found(self):
        self.mock_compute_client.return_value.gallery_images.get.side_effect = ResourceNotFoundError("Not found")

        self.manager.check_or_create_gallery_image("bosh-azure-hyperv-ubuntu-jammy-go_agent", "gallery", "img")

        self.mock_logger.info.assert_any_call("Creating new gallery image definition...")
        self.mock_compute_client.return_value.gallery_images.begin_create_or_update.assert_called_once_with(
            resource_group_name="test-rg",
            gallery_name="gallery",
            gallery_image_name="img",
            gallery_image=unittest.mock.ANY
        )

    def test_gallery_image_version_exists_true(self):
        self.mock_compute_client.return_value.gallery_images.get.return_value = GalleryImageVersion(
            id="test",
            location="test",
            tags={},
            os_type="test",
            os_state="test",
            publishing_profile=None
        )

        result = self.manager.gallery_image_version_exists("gallery", "img", "ver")

        self.assertTrue(result)

def make_mock_container_client(blob_service_client: ComputeManagementClient, exists: bool = True) -> ContainerClient:
    mock_container_client = MagicMock()
    mock_container_client.upload_blob.return_value = mock_container_client
    mock_container_client.exists.return_value = exists
    blob_service_client.return_value.get_container_client.return_value = mock_container_client
    return mock_container_client

if __name__ == '__main__':
    unittest.main()