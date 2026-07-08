import logging
import sys

from .azure_manager import AzureManager
from .config import (
    AzureConfig,
    MirrorConfig,
    configure_notifier,
    load_azure_config,
    load_mirror_config,
)
from .mirror.bosh_io import BoshIoJammyMirror, BoshIoNobleMirror, BoshIoStemcellMirror
from .notify.notifier import Notifier

MIRROR_TYPES: tuple[type[BoshIoStemcellMirror], ...] = (BoshIoJammyMirror, BoshIoNobleMirror)


def configure_logging() -> logging.Logger:
    """Configure application logging and return the app logger."""
    app_logger = logging.getLogger("stemcell_mirror")
    app_logger.setLevel(logging.INFO)
    handler = logging.StreamHandler(stream=sys.stdout)
    app_logger.addHandler(handler)

    # Azure SDK logs are too verbose, so we'll suppress them.
    az_logger = logging.getLogger("azure")
    az_logger.setLevel(logging.WARNING)
    az_logger.addHandler(handler)

    return app_logger


def build_mirror(
    azure_manager: AzureManager,
    azure_config: AzureConfig,
    mirror_config: MirrorConfig,
    notifier: Notifier | None,
    logger: logging.Logger,
) -> BoshIoStemcellMirror:
    """Build the stemcell mirror for the configured mirror key."""
    for mirror_cls in MIRROR_TYPES:
        if mirror_cls.name == mirror_config.mirror:
            return mirror_cls(
                azure_manager=azure_manager,
                gallery_name=azure_config.gallery_name,
                extraction_directory=mirror_config.mounted_directory,
                notifier=notifier,
                logger=logger,
            )

    supported = ", ".join(cls.name for cls in MIRROR_TYPES)
    raise ValueError(f"Unsupported mirror '{mirror_config.mirror}'. Supported mirrors: {supported}")


def main() -> int:
    logger = configure_logging()

    logger.info("Loading configuration...")
    azure_config = load_azure_config()
    mirror_config = load_mirror_config()

    logger.info("Setting up Azure Manager...")
    azure_manager = AzureManager(
        subscription_id=azure_config.subscription_id,
        client_id=azure_config.managed_identity_client_id,
        resource_group=azure_config.resource_group,
        location=azure_config.location,
        logger=logger,
    )
    azure_manager.setup_storage(azure_config.storage_account_name, azure_config.storage_container)

    notifier = configure_notifier(logger)

    mirror = build_mirror(azure_manager, azure_config, mirror_config, notifier, logger)
    mirror_name = type(mirror).__name__

    logger.info("Starting %s for mirror '%s'...", mirror_name, mirror_config.mirror)
    mirror.run()
    logger.info("Completed %s.", mirror_name)

    return 0


if __name__ == "__main__":
    sys.exit(main())
