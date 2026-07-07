import logging
import unittest
from unittest.mock import MagicMock

from src.config import AzureConfig, MirrorConfig
from src.main import build_mirror
from src.mirror.bosh_io import BoshIoJammyMirror, BoshIoNobleMirror


class TestBuildMirror(unittest.TestCase):
    def setUp(self) -> None:
        self.azure_manager = MagicMock()
        self.azure_config = AzureConfig(
            subscription_id="sub",
            managed_identity_client_id="identity",
            resource_group="rg",
            storage_account_name="storage",
            location="eastus",
            gallery_name="test-gallery",
        )
        self.logger = logging.getLogger("test")

    def _mirror_config(self, series: str) -> MirrorConfig:
        return MirrorConfig(stemcell_series=series, mounted_directory="/tmp")

    def test_build_jammy_mirror(self):
        mirror = build_mirror(
            self.azure_manager,
            self.azure_config,
            self._mirror_config("bosh-azure-hyperv-ubuntu-jammy-go_agent"),
            None,
            self.logger,
        )

        self.assertIsInstance(mirror, BoshIoJammyMirror)
        self.assertEqual(mirror.gallery_name, "test-gallery")
        self.assertEqual(mirror.extraction_directory, "/tmp")

    def test_build_noble_mirror(self):
        mirror = build_mirror(
            self.azure_manager,
            self.azure_config,
            self._mirror_config("bosh-azure-hyperv-ubuntu-noble"),
            None,
            self.logger,
        )

        self.assertIsInstance(mirror, BoshIoNobleMirror)

    def test_build_unsupported_series_raises(self):
        with self.assertRaises(ValueError):
            build_mirror(
                self.azure_manager,
                self.azure_config,
                self._mirror_config("bosh-azure-hyperv-ubuntu-xenial-go_agent"),
                None,
                self.logger,
            )


if __name__ == "__main__":
    unittest.main()
