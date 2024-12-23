import os
import json
import shutil
import requests
import unittest
from unittest.mock import patch, MagicMock
from mirror.stemcell_mirror import StemcellMirror

tmp_dir = os.path.join("tests", "tmp")

class TestStemcellMirror(unittest.TestCase):

    def setUp(self):
        self.mock_azure_manager = MagicMock()
        self.mirror = StemcellMirror(
            azure_manager=self.mock_azure_manager,
            extraction_directory=tmp_dir,
        )
        if os.path.isdir(tmp_dir):
            shutil.rmtree(tmp_dir)
        os.makedirs(tmp_dir, exist_ok=True)
        shutil.copy(os.path.join("tests", "resources", "fake-stemcell.tgz"), tmp_dir)

    def tearDown(self):
        shutil.rmtree(tmp_dir)

    @patch("mirror.stemcell_mirror.StemcellMirror._download_stemcell")
    @patch("requests.get")
    def test_run_with_stemcell_resources(self, mock_requests_get, mock_download_stemcell):
        mock_response_api = MagicMock()
        mock_response_api.status_code = 200
        with open("tests/resources/stemcell.json", "r") as mock_data:
            mock_response_api.json.return_value = json.load(mock_data)
        mock_response_api.raise_for_status = MagicMock()
        mock_requests_get.return_value = mock_response_api
        mock_download_stemcell.return_value = os.path.join(tmp_dir, "fake-stemcell.tgz")
        self.mock_azure_manager.gallery_image_version_exists.return_value = False

        self.mirror.run("bosh-azure-hyperv-ubuntu-jammy-go_agent", "test-gallery", "test-image")

        self.mock_azure_manager.gallery_image_version_exists.assert_called_once_with(
            "test-gallery",
            "test-image",
            "1.682.0"
        )
        self.mock_azure_manager.check_or_create_gallery_image.assert_called_once_with(
            "bosh-azure-hyperv-ubuntu-jammy-go_agent",
            "test-gallery",
            "test-image"
        )
        self.mock_azure_manager.upload_vhd.assert_called_once_with(os.path.join(tmp_dir, "root.vhd"))
        self.mock_azure_manager.create_gallery_image_version.assert_called_once()

    @patch("requests.get")
    def test_run_with_existing_version(self, mock_requests_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {
                "version": "1.682.0",
                "regular": {"url": "https://fake-url/stemcell.tgz"}
            }
        ]
        mock_response.raise_for_status = MagicMock()
        mock_requests_get.return_value = mock_response
        self.mock_azure_manager.gallery_image_version_exists.return_value = True

        self.mirror.run("ubuntu-jammy", "test-gallery", "test-image")

        self.mock_azure_manager.gallery_image_version_exists.assert_called_once_with(
            "test-gallery",
            "test-image",
            "1.682.0"
        )
        self.mock_azure_manager.check_or_create_gallery_image.assert_not_called()
        self.mock_azure_manager.upload_vhd.assert_not_called()
        self.mock_azure_manager.create_gallery_image_version.assert_not_called()

    @patch("requests.get")
    def test_run_no_download_url(self, mock_requests_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [{"version": "45.6"}]  # No 'regular.url'
        mock_response.raise_for_status = MagicMock()
        mock_requests_get.return_value = mock_response

        with self.assertRaises(ValueError) as context:
            self.mirror.run("ubuntu-jammy", "test-gallery", "test-image")

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
            self.mirror.run("ubuntu-jammy", "test-gallery", "test-image")

        self.mock_azure_manager.gallery_image_version_exists.assert_not_called()
        self.mock_azure_manager.check_or_create_gallery_image.assert_not_called()
        self.mock_azure_manager.upload_vhd.assert_not_called()
        self.mock_azure_manager.create_gallery_image_version.assert_not_called()

if __name__ == '__main__':
    unittest.main()