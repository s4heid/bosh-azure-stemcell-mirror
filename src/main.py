import os
import sys
import logging

from mirror.azure_manager import AzureManager
from mirror.notify import GitHubNotifier, GitHubNotifierConfig, Notifier
from mirror.stemcell_mirror import StemcellMirror

# required environment variables
subscription_id: str = os.environ["AZURE_SUBSCRIPTION_ID"]
managed_identity_client_id: str = os.environ["AZURE_MANAGED_IDENTITY_ID"]
resource_group: str = os.environ["AZURE_RESOURCE_GROUP"]
storage_account_name: str = os.environ["AZURE_STORAGE_ACCOUNT_NAME"]

# optional environment variables with defaults
location: str = os.environ.get("AZURE_REGION", "eastus")
gallery_name: str = os.environ.get("AZURE_GALLERY_NAME", "bosh-azure-stemcells")
stemcell_series: str = os.environ.get("BASM_STEMCELL_SERIES", "bosh-azure-hyperv-ubuntu-jammy-go_agent")
gallery_image_name: str = os.environ.get("BASM_GALLERY_IMAGE_NAME", stemcell_series)
mounted_dir: str = os.environ.get("BASM_MOUNTED_DIRECTORY", "")


def configure_notifier(app_logger: logging.Logger) -> Notifier | None:
    github_token: str | None = os.environ.get("BASM_NOTIFY_GITHUB_TOKEN")
    if not github_token:
        app_logger.info("GitHub workflow notifications disabled; BASM_NOTIFY_GITHUB_TOKEN not set.")
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
        repository_owner=required_vars["BASM_NOTIFY_GITHUB_OWNER"],
        repository_name=required_vars["BASM_NOTIFY_GITHUB_REPO"],
        workflow_identifier=required_vars["BASM_NOTIFY_GITHUB_WORKFLOW"],
        ref=required_vars["BASM_NOTIFY_GITHUB_REF"],
        token=github_token,
        timeout_seconds=10,
    )
    return GitHubNotifier(config, logger=app_logger)


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
    azure_manager.setup_storage(storage_account_name, "stemcell")

    app_logger.info("Starting stemcell mirror run...")

    notifier = configure_notifier(app_logger)

    mirror: StemcellMirror = StemcellMirror(azure_manager, mounted_dir, notifier=notifier, logger=app_logger)
    mirror.run(stemcell_series, gallery_name, gallery_image_name)

    app_logger.info("Completed stemcell mirror run.")
