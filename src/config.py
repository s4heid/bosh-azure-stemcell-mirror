import logging
import os
from dataclasses import dataclass

from .notify.github import GitHubNotifier, GitHubNotifierConfig
from .notify.notifier import Notifier

# Default bosh.io stemcell series to mirror when BASM_STEMCELL_SERIES is unset.
DEFAULT_STEMCELL_SERIES = "bosh-azure-hyperv-ubuntu-jammy-go_agent"


@dataclass(frozen=True)
class AzureConfig:
    """Configuration for the Azure environment, read from environment variables."""

    subscription_id: str
    managed_identity_client_id: str
    resource_group: str
    storage_account_name: str
    location: str
    gallery_name: str
    storage_container: str = "stemcell"


@dataclass(frozen=True)
class MirrorConfig:
    """Runtime configuration for the stemcell mirror."""

    stemcell_series: str
    mounted_directory: str


def load_azure_config() -> AzureConfig:
    """Read the Azure configuration from environment variables."""
    return AzureConfig(
        subscription_id=os.environ["AZURE_SUBSCRIPTION_ID"],
        managed_identity_client_id=os.environ["AZURE_MANAGED_IDENTITY_ID"],
        resource_group=os.environ["AZURE_RESOURCE_GROUP"],
        storage_account_name=os.environ["AZURE_STORAGE_ACCOUNT_NAME"],
        location=os.environ.get("AZURE_REGION", "eastus"),
        gallery_name=os.environ.get("AZURE_GALLERY_NAME", "bosh-azure-stemcells"),
    )


def load_mirror_config() -> MirrorConfig:
    """Read the stemcell mirror runtime configuration from environment variables."""
    return MirrorConfig(
        stemcell_series=os.environ.get("BASM_STEMCELL_SERIES", DEFAULT_STEMCELL_SERIES),
        mounted_directory=os.environ.get("BASM_MOUNTED_DIRECTORY", ""),
    )


def configure_notifier(logger: logging.Logger) -> Notifier | None:
    """Build a notifier from environment variables, or ``None`` if disabled."""
    github_token: str | None = os.environ.get("BASM_NOTIFY_GITHUB_TOKEN")
    if not github_token:
        logger.info("GitHub workflow notifications disabled; BASM_NOTIFY_GITHUB_TOKEN not set.")
        return None

    required_vars = {
        "BASM_NOTIFY_GITHUB_OWNER": os.environ.get("BASM_NOTIFY_GITHUB_OWNER"),
        "BASM_NOTIFY_GITHUB_REPO": os.environ.get("BASM_NOTIFY_GITHUB_REPO"),
        "BASM_NOTIFY_GITHUB_WORKFLOW": os.environ.get("BASM_NOTIFY_GITHUB_WORKFLOW"),
        "BASM_NOTIFY_GITHUB_REF": os.environ.get("BASM_NOTIFY_GITHUB_REF"),
    }
    missing = [name for name, value in required_vars.items() if not value]
    if missing:
        raise ValueError("Missing required GitHub notification environment variables: " + ", ".join(missing))

    config = GitHubNotifierConfig(
        api_base_url=os.environ.get("BASM_NOTIFY_GITHUB_API_URL", "https://api.github.com"),
        repository_owner=os.environ["BASM_NOTIFY_GITHUB_OWNER"],
        repository_name=os.environ["BASM_NOTIFY_GITHUB_REPO"],
        workflow_identifier=os.environ["BASM_NOTIFY_GITHUB_WORKFLOW"],
        ref=os.environ["BASM_NOTIFY_GITHUB_REF"],
        token=github_token,
        timeout_seconds=10,
    )
    return GitHubNotifier(config, logger=logger)
