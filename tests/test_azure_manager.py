import unittest
import unittest.mock
from unittest.mock import MagicMock, mock_open, patch

from azure.core.exceptions import ResourceNotFoundError

from src.azure_manager import AzureManager, _normalize_architecture


class TestAzureManager(unittest.TestCase):
    @patch("src.azure_manager.DefaultAzureCredential")
    @patch("src.azure_manager.ComputeManagementClient")
    def setUp(self, mock_compute_client: MagicMock, mock_credential: MagicMock) -> None:
        self.mock_logger = MagicMock()
        self.manager = AzureManager(
            subscription_id="test-subscription-id",
            client_id="test-client-id",
            resource_group="test-rg",
            location="test-location",
            logger=self.mock_logger,
        )
        self.mock_compute_client = mock_compute_client

    @patch("src.azure_manager.BlobServiceClient")
    def test_setup_storage(self, mock_blob_service_client: MagicMock) -> None:
        mock_container_client = make_mock_container_client(mock_blob_service_client, exists=False)

        self.manager.setup_storage("teststorage123", "testcontainer123")

        self.assertEqual(self.manager.storage_account_name, "teststorage123")
        self.assertEqual(self.manager.storage_container, "testcontainer123")
        mock_container_client.create_container.assert_called_once()

    @patch("src.azure_manager.BlobServiceClient")
    def test_upload_vhd(self, mock_blob_service_client: MagicMock) -> None:
        mock_container_client = make_mock_container_client(mock_blob_service_client)
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
            max_concurrency=unittest.mock.ANY,
        )
        self.assertTrue(
            any(
                call.args[0].startswith("Uploaded VHD to blob: bosh-stemcell-")
                for call in self.mock_logger.info.mock_calls
            ),
            "Expected log message starting with 'Uploaded VHD to blob: '",
        )

    def test_upload_vhd_no_storage_config_raises(self):
        with self.assertRaises(ValueError):
            self.manager.upload_vhd("fake.vhd")

    def test_check_or_create_gallery_image_exists(self):
        self.mock_compute_client.return_value.gallery_images.get.return_value = MagicMock()

        self.manager.check_or_create_gallery_image("series", "gallery", "img")

        self.mock_logger.info.assert_any_call("Gallery image definition already exists.")
        self.mock_compute_client.return_value.gallery_images.begin_create_or_update.assert_not_called()

    def test_check_or_create_gallery_image_not_found(self):
        self.mock_compute_client.return_value.gallery_images.get.side_effect = ResourceNotFoundError("Not found")

        self.manager.check_or_create_gallery_image("bosh-azure-hyperv-ubuntu-jammy-go_agent", "gallery", "img")

        self.mock_logger.info.assert_any_call("Creating new gallery image definition...")
        begin = self.mock_compute_client.return_value.gallery_images.begin_create_or_update
        begin.assert_called_once()
        gallery_image = begin.call_args.kwargs["gallery_image"]
        self.assertEqual(gallery_image.os_type, "Linux")
        self.assertEqual(gallery_image.os_state, "Generalized")
        self.assertEqual(gallery_image.hyper_v_generation, "V1")
        self.assertEqual(gallery_image.identifier.sku, "gen1")
        self.assertIsNone(gallery_image.features)

    def test_check_or_create_gallery_image_gen2_features(self):
        self.mock_compute_client.return_value.gallery_images.get.side_effect = ResourceNotFoundError("Not found")
        cloud_properties = {
            "generation": "gen2",
            "architecture": "x86_64",
            "accelerated_networking": True,
            "hibernation": True,
            "disk_controller_types": ["scsi", "nvme"],
            "security_type": "TrustedLaunchSupported",
        }

        self.manager.check_or_create_gallery_image("noble", "gallery", "img", cloud_properties)

        begin = self.mock_compute_client.return_value.gallery_images.begin_create_or_update
        gallery_image = begin.call_args.kwargs["gallery_image"]
        self.assertEqual(gallery_image.hyper_v_generation, "V2")
        self.assertEqual(gallery_image.os_state, "Generalized")
        self.assertEqual(gallery_image.architecture, "x64")
        self.assertEqual(gallery_image.identifier.sku, "gen2")
        features = {feature.name: feature.value for feature in gallery_image.features}
        self.assertEqual(features["DiskControllerTypes"], "SCSI,NVMe")
        self.assertEqual(features["IsAcceleratedNetworkSupported"], "True")
        self.assertEqual(features["IsHibernateSupported"], "True")
        self.assertEqual(features["SecurityType"], "TrustedLaunchSupported")

    def test_check_or_create_gallery_image_gen1_omits_features(self):
        self.mock_compute_client.return_value.gallery_images.get.side_effect = ResourceNotFoundError("Not found")
        cloud_properties = {
            "generation": "gen1",
            "accelerated_networking": True,
            "disk_controller_types": ["scsi"],
        }

        self.manager.check_or_create_gallery_image("jammy", "gallery", "img", cloud_properties)

        begin = self.mock_compute_client.return_value.gallery_images.begin_create_or_update
        gallery_image = begin.call_args.kwargs["gallery_image"]
        self.assertEqual(gallery_image.hyper_v_generation, "V1")
        self.assertIsNone(gallery_image.features)

    def test_check_or_create_gallery_image_invalid_disk_controllers(self):
        self.mock_compute_client.return_value.gallery_images.get.side_effect = ResourceNotFoundError("Not found")
        cloud_properties = {"generation": "gen2", "disk_controller_types": "not-a-list"}

        self.manager.check_or_create_gallery_image("noble", "gallery", "img", cloud_properties)

        self.mock_logger.warning.assert_any_call("Ignoring invalid 'disk_controller_types' metadata: not-a-list")
        begin = self.mock_compute_client.return_value.gallery_images.begin_create_or_update
        gallery_image = begin.call_args.kwargs["gallery_image"]
        self.assertIsNone(gallery_image.features)

    def test_normalize_architecture(self):
        self.assertEqual(_normalize_architecture("x86_64"), "x64")
        self.assertEqual(_normalize_architecture("x64"), "x64")
        self.assertEqual(_normalize_architecture("arm64"), "Arm64")
        self.assertEqual(_normalize_architecture("ARM64"), "Arm64")
        self.assertIsNone(_normalize_architecture(None))
        self.assertIsNone(_normalize_architecture(""))

    def test_gallery_image_version_exists_true(self):
        self.mock_compute_client.return_value.gallery_image_versions.get.return_value = MagicMock()

        result = self.manager.gallery_image_version_exists("gallery", "img", "ver")

        self.assertTrue(result)


def make_mock_container_client(blob_service_client: MagicMock, exists: bool = True) -> MagicMock:
    mock_container_client = MagicMock()
    mock_container_client.upload_blob.return_value = mock_container_client
    mock_container_client.exists.return_value = exists
    blob_service_client.return_value.get_container_client.return_value = mock_container_client
    return mock_container_client


if __name__ == "__main__":
    unittest.main()
