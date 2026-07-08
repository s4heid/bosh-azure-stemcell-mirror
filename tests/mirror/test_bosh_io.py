import json
import os
import shutil
import unittest
from unittest.mock import MagicMock, patch

import requests

from src.mirror.bosh_io import BoshIoJammyMirror, BoshIoNobleMirror, BoshIoStemcellMirror

tmp_dir = os.path.join("tests", "tmp")

JAMMY_SERIES = "bosh-azure-hyperv-ubuntu-jammy-go_agent"


class TestBoshIoStemcellMirror(unittest.TestCase):

    def setUp(self):
        self.mock_azure_manager = MagicMock()
        self.mock_azure_manager.subscription_id = "00000000-0000-0000-0000-000000000000"
        self.mock_azure_manager.resource_group = "test-resource-group"
        self.mirror = BoshIoJammyMirror(
            azure_manager=self.mock_azure_manager,
            gallery_name="test-gallery",
            gallery_image_name="test-image",
            extraction_directory=tmp_dir,
        )
        if os.path.isdir(tmp_dir):
            shutil.rmtree(tmp_dir)
        os.makedirs(tmp_dir, exist_ok=True)
        shutil.copy(os.path.join("tests", "resources", "fake-stemcell.tgz"), tmp_dir)

    def tearDown(self):
        shutil.rmtree(tmp_dir)

    @patch("src.mirror.bosh_io.BoshIoStemcellMirror._download_stemcell")
    @patch("requests.get")
    def test_run_with_stemcell_resources(self, mock_requests_get, mock_download_stemcell):
        mock_response_api = MagicMock()
        mock_response_api.status_code = 200
        with open("tests/resources/stemcell.json") as mock_data:
            mock_response_api.json.return_value = json.load(mock_data)
        mock_response_api.raise_for_status = MagicMock()
        mock_requests_get.return_value = mock_response_api
        mock_download_stemcell.return_value = os.path.join(tmp_dir, "fake-stemcell.tgz")
        self.mock_azure_manager.gallery_image_version_exists.return_value = False

        self.mirror.run()

        self.mock_azure_manager.gallery_image_version_exists.assert_called_once_with(
            "test-gallery", "test-image", "1.682.0"
        )
        self.mock_azure_manager.check_or_create_gallery_image.assert_called_once()
        call_args = self.mock_azure_manager.check_or_create_gallery_image.call_args
        self.assertEqual(call_args.args[:3], (JAMMY_SERIES, "test-gallery", "test-image"))
        passed_cloud_properties = call_args.args[3]
        self.assertEqual(passed_cloud_properties["architecture"], "x86_64")
        self.assertEqual(passed_cloud_properties["os_type"], "linux")
        self.mock_azure_manager.upload_vhd.assert_called_once_with(os.path.join(tmp_dir, "root.vhd"))
        self.mock_azure_manager.create_gallery_image_version.assert_called_once()

    @patch("requests.get")
    def test_run_with_existing_version(self, mock_requests_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [{"version": "1.682.0", "regular": {"url": "https://fake-url/stemcell.tgz"}}]
        mock_response.raise_for_status = MagicMock()
        mock_requests_get.return_value = mock_response
        self.mock_azure_manager.gallery_image_version_exists.return_value = True

        self.mirror.run()

        self.mock_azure_manager.gallery_image_version_exists.assert_called_once_with(
            "test-gallery", "test-image", "1.682.0"
        )
        self.mock_azure_manager.check_or_create_gallery_image.assert_not_called()
        self.mock_azure_manager.upload_vhd.assert_not_called()
        self.mock_azure_manager.create_gallery_image_version.assert_not_called()

    @patch("requests.get")
    def test_run_with_empty_stemcell_list(self, mock_requests_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = []
        mock_response.raise_for_status = MagicMock()
        mock_requests_get.return_value = mock_response

        self.mirror.run()

        self.mock_azure_manager.gallery_image_version_exists.assert_not_called()
        self.mock_azure_manager.check_or_create_gallery_image.assert_not_called()
        self.mock_azure_manager.upload_vhd.assert_not_called()
        self.mock_azure_manager.create_gallery_image_version.assert_not_called()

    @patch("src.mirror.bosh_io.BoshIoStemcellMirror._download_stemcell")
    @patch("requests.get")
    def test_run_triggers_notifier_on_new_upload(self, mock_requests_get, mock_download_stemcell):
        mock_notifier = MagicMock()
        mirror_with_notifier = BoshIoJammyMirror(
            azure_manager=self.mock_azure_manager,
            gallery_name="test-gallery",
            gallery_image_name="test-image",
            extraction_directory=tmp_dir,
            notifier=mock_notifier,
        )

        mock_response_api = MagicMock()
        mock_response_api.status_code = 200
        with open("tests/resources/stemcell.json") as mock_data:
            mock_response_api.json.return_value = json.load(mock_data)
        mock_response_api.raise_for_status = MagicMock()
        mock_requests_get.return_value = mock_response_api
        mock_download_stemcell.return_value = os.path.join(tmp_dir, "fake-stemcell.tgz")
        self.mock_azure_manager.gallery_image_version_exists.return_value = False

        mirror_with_notifier.run()

        mock_notifier.notify_new_stemcell.assert_called_once_with(
            {
                "gallery_name": "test-gallery",
                "gallery_image_name": "test-image",
                "gallery_image_version": "1.682.0",
                "gallery_subscription_id": "00000000-0000-0000-0000-000000000000",
                "gallery_resource_group": "test-resource-group",
            },
        )

    @patch("requests.get")
    def test_run_no_download_url(self, mock_requests_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [{"version": "45.6"}]  # No 'regular.url'
        mock_response.raise_for_status = MagicMock()
        mock_requests_get.return_value = mock_response

        with self.assertRaises(ValueError) as context:
            self.mirror.run()

        self.assertIn("Failed to find download URL for stemcell.", str(context.exception))
        self.mock_azure_manager.gallery_image_version_exists.assert_not_called()
        self.mock_azure_manager.check_or_create_gallery_image.assert_not_called()
        self.mock_azure_manager.upload_vhd.assert_not_called()
        self.mock_azure_manager.create_gallery_image_version.assert_not_called()

    @patch("requests.get")
    def test_run_raise_for_status_exception(self, mock_requests_get):
        mock_response_api = MagicMock()
        mock_response_api.status_code = 404
        mock_response_api.raise_for_status.side_effect = requests.exceptions.HTTPError("Not Found")
        mock_requests_get.return_value = mock_response_api

        with self.assertRaises(requests.exceptions.HTTPError):
            self.mirror.run()

        self.mock_azure_manager.gallery_image_version_exists.assert_not_called()
        self.mock_azure_manager.check_or_create_gallery_image.assert_not_called()
        self.mock_azure_manager.upload_vhd.assert_not_called()
        self.mock_azure_manager.create_gallery_image_version.assert_not_called()

    def test_concrete_mirrors_series_and_default_image_name(self):
        jammy = BoshIoJammyMirror(azure_manager=self.mock_azure_manager, gallery_name="gallery")
        noble = BoshIoNobleMirror(azure_manager=self.mock_azure_manager, gallery_name="gallery")

        self.assertEqual(jammy.name, "boshio/ubuntu-jammy")
        self.assertEqual(noble.name, "boshio/ubuntu-noble")
        self.assertEqual(jammy.stemcell_series, JAMMY_SERIES)
        self.assertEqual(noble.stemcell_series, "bosh-azure-hyperv-ubuntu-noble")
        self.assertEqual(jammy.gallery_image_name, JAMMY_SERIES)
        self.assertEqual(noble.gallery_image_name, "bosh-azure-hyperv-ubuntu-noble")

    def test_base_mirror_requires_stemcell_series(self):
        with self.assertRaises(ValueError):
            BoshIoStemcellMirror(azure_manager=self.mock_azure_manager, gallery_name="gallery")

    def test_read_cloud_properties(self):
        manifest = (
            "---\n"
            "name: bosh-azure-hyperv-ubuntu-noble\n"
            "version: '1.1'\n"
            "cloud_properties:\n"
            "  os_type: linux\n"
            "  architecture: x86_64\n"
            "  generation: gen2\n"
            "  accelerated_networking: true\n"
            "  hibernation: true\n"
            "  disk_controller_types:\n"
            "  - scsi\n"
            "  - nvme\n"
            "  security_type: TrustedLaunchSupported\n"
        )
        with open(os.path.join(tmp_dir, "stemcell.MF"), "w") as manifest_file:
            manifest_file.write(manifest)

        cloud_properties = self.mirror._read_cloud_properties(tmp_dir)

        self.assertEqual(cloud_properties["generation"], "gen2")
        self.assertEqual(cloud_properties["architecture"], "x86_64")
        self.assertTrue(cloud_properties["accelerated_networking"])
        self.assertTrue(cloud_properties["hibernation"])
        self.assertEqual(cloud_properties["disk_controller_types"], ["scsi", "nvme"])
        self.assertEqual(cloud_properties["security_type"], "TrustedLaunchSupported")

    def test_read_cloud_properties_missing_manifest(self):
        missing_dir = os.path.join(tmp_dir, "empty")
        os.makedirs(missing_dir, exist_ok=True)

        cloud_properties = self.mirror._read_cloud_properties(missing_dir)

        self.assertEqual(cloud_properties, {})


if __name__ == "__main__":
    unittest.main()
