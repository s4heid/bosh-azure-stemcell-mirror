import unittest
from unittest.mock import MagicMock, patch

from src.config import configure_notifier, load_azure_config, load_mirror_config
from src.notify.github import GitHubNotifier


class TestConfig(unittest.TestCase):
    def setUp(self) -> None:
        self.logger = MagicMock()

    @patch.dict("os.environ", {}, clear=True)
    def test_configure_notifier_disabled_without_token(self):
        self.assertIsNone(configure_notifier(self.logger))

    @patch.dict("os.environ", {"BASM_NOTIFY_GITHUB_TOKEN": "token"}, clear=True)
    def test_configure_notifier_missing_vars_raises(self):
        with self.assertRaises(ValueError):
            configure_notifier(self.logger)

    @patch.dict(
        "os.environ",
        {
            "BASM_NOTIFY_GITHUB_TOKEN": "token",
            "BASM_NOTIFY_GITHUB_OWNER": "owner",
            "BASM_NOTIFY_GITHUB_REPO": "repo",
            "BASM_NOTIFY_GITHUB_WORKFLOW": "sync.yml",
            "BASM_NOTIFY_GITHUB_REF": "main",
        },
        clear=True,
    )
    def test_configure_notifier_builds_github_notifier(self):
        notifier = configure_notifier(self.logger)
        self.assertIsInstance(notifier, GitHubNotifier)

    @patch.dict(
        "os.environ",
        {
            "AZURE_SUBSCRIPTION_ID": "sub",
            "AZURE_MANAGED_IDENTITY_ID": "identity",
            "AZURE_RESOURCE_GROUP": "rg",
            "AZURE_STORAGE_ACCOUNT_NAME": "storage",
        },
        clear=True,
    )
    def test_load_azure_config_uses_defaults(self):
        config = load_azure_config()

        self.assertEqual(config.subscription_id, "sub")
        self.assertEqual(config.managed_identity_client_id, "identity")
        self.assertEqual(config.location, "eastus")
        self.assertEqual(config.gallery_name, "bosh-azure-stemcells")
        self.assertEqual(config.storage_container, "stemcell")

    @patch.dict("os.environ", {}, clear=True)
    def test_load_azure_config_missing_required_raises(self):
        with self.assertRaises(KeyError):
            load_azure_config()

    @patch.dict("os.environ", {"BASM_MOUNTED_DIRECTORY": "/mnt/data"}, clear=True)
    def test_load_mirror_config_defaults_to_jammy(self):
        config = load_mirror_config()

        self.assertEqual(config.mounted_directory, "/mnt/data")
        self.assertEqual(config.stemcell_series, "bosh-azure-hyperv-ubuntu-jammy-go_agent")

    @patch.dict(
        "os.environ",
        {"BASM_STEMCELL_SERIES": "bosh-azure-hyperv-ubuntu-noble"},
        clear=True,
    )
    def test_load_mirror_config_reads_series(self):
        config = load_mirror_config()

        self.assertEqual(config.stemcell_series, "bosh-azure-hyperv-ubuntu-noble")
        self.assertEqual(config.mounted_directory, "")


if __name__ == "__main__":
    unittest.main()
