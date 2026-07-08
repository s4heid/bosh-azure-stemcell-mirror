import logging
import os
import shutil
import tarfile
import tempfile

import requests
import yaml
from semver.version import Version

from ..azure_manager import AzureManager
from ..notify.notifier import Notifier
from .stemcell_mirror import StemcellMirror


class BoshIoStemcellMirror(StemcellMirror):
    """Mirrors a bosh.io stemcell series to an Azure Compute Gallery.

    Concrete subclasses declare the ``stemcell_series`` they are responsible for.
    """

    STEMCELL_API_URL = "https://bosh.io/api/v1/stemcells/"
    stemcell_series: str = ""

    def __init__(
        self,
        azure_manager: AzureManager,
        gallery_name: str,
        gallery_image_name: str | None = None,
        extraction_directory: str = "",
        notifier: Notifier | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        if not self.stemcell_series:
            raise ValueError("stemcell_series must be set by a subclass.")
        self.azure_manager: AzureManager = azure_manager
        self.gallery_name: str = gallery_name
        self.gallery_image_name: str = gallery_image_name or self.stemcell_series
        self.extraction_directory: str = extraction_directory
        self.notifier: Notifier | None = notifier
        self.logger: logging.Logger = logger or logging.getLogger(__name__)

    def run(self) -> None:
        """
        Mirrors the latest stemcell of this series to Azure.

        Checks bosh.io for the latest stemcell version, downloads it if it's a
        new version, extracts the .vhd file, uploads it to Azure storage, and
        creates a new gallery image version in Azure.
        """
        response: requests.Response = requests.get(f"{self.STEMCELL_API_URL}{self.stemcell_series}")
        response.raise_for_status()
        stemcells: list[dict] = response.json()

        if not stemcells:
            self.logger.info(f"No stemcells found for series '{self.stemcell_series}'.")
            return

        latest_stemcell: dict = stemcells[0]
        latest_version: str | None = latest_stemcell.get("version")
        if not latest_version:
            raise ValueError(f"Latest stemcell for series '{self.stemcell_series}' is missing a version.")
        sc_version: Version = Version.parse(latest_version, optional_minor_and_patch=True)
        formatted_latest_version: str = f"{sc_version.major}.{sc_version.minor}.{sc_version.patch}"
        download_url: str | None = latest_stemcell.get("regular", {}).get("url")
        if not download_url:
            raise ValueError("Failed to find download URL for stemcell.")

        version_exists: bool = self.azure_manager.gallery_image_version_exists(
            self.gallery_name, self.gallery_image_name, formatted_latest_version
        )
        if version_exists:
            self.logger.info("No new stemcell to upload.")
            return

        self.logger.info(f"New stemcell version {formatted_latest_version} found. Downloading...")
        extracted_stemcell_dir: str = self._create_extraction_dir()
        try:
            stemcell_path: str = self._download_stemcell(download_url, extracted_stemcell_dir)
            vhd_path: str = self._extract_stemcell(stemcell_path)

            if not os.path.exists(vhd_path):
                raise FileNotFoundError("Failed to find root.vhd in stemcell image.")

            cloud_properties: dict = self._read_cloud_properties(os.path.dirname(vhd_path))

            self.logger.info("Checking gallery image definition.")
            self.azure_manager.check_or_create_gallery_image(
                self.stemcell_series, self.gallery_name, self.gallery_image_name, cloud_properties
            )

            self.logger.info("Uploading .vhd to Azure storage...")
            blob_uri: str = self.azure_manager.upload_vhd(vhd_path)

            self.logger.info(f"Creating new gallery image version {formatted_latest_version}...")
            self.azure_manager.create_gallery_image_version(
                self.gallery_name, self.gallery_image_name, formatted_latest_version, blob_uri
            )

            self.logger.info("Completed vhd upload and gallery image version creation.")

            if self.notifier:
                self._notify_new_stemcell(formatted_latest_version)
        finally:
            self.logger.info(f"Cleaning up temp directory: {extracted_stemcell_dir}")
            shutil.rmtree(extracted_stemcell_dir, ignore_errors=True)

    def _notify_new_stemcell(self, version: str) -> None:
        notifier = self.notifier
        if notifier is None:
            return
        metadata: dict[str, str] = {
            "gallery_name": self.gallery_name,
            "gallery_image_name": self.gallery_image_name,
            "gallery_image_version": version,
            "gallery_subscription_id": self.azure_manager.subscription_id,
            "gallery_resource_group": self.azure_manager.resource_group,
        }
        self.logger.info("Dispatching notifications for new stemcell version %s...", version)
        notifier.notify_new_stemcell(metadata)

    def _download_stemcell(self, url: str, extract_path: str) -> str:
        """
        Downloads the stemcell archive.

        Args:
            url (str): The URL to download the stemcell from.
            extract_path (str): The directory to download the stemcell.

        Returns:
            str: The path to the downloaded stemcell tarball.
        """
        response: requests.Response = requests.get(url, stream=True)
        tgz_path: str = os.path.join(extract_path, "stemcell.tgz")

        with open(tgz_path, "wb") as temp_tgz:
            for chunk in response.iter_content(chunk_size=8192):
                temp_tgz.write(chunk)

        return tgz_path

    def _extract_stemcell(self, stemcell_path: str) -> str:
        """
        Extracts the VHD from the stemcell tarball.

        Args:
            stemcell_path (str): The tarfile to extract the VHD from.

        Returns:
            str: The path to the extracted VHD.
        """
        extract_path = os.path.dirname(stemcell_path)
        with tarfile.open(stemcell_path, "r:gz") as tar:
            tar.extractall(extract_path)

        image_path: str = os.path.join(extract_path, "image")
        with tarfile.open(image_path, "r:*") as image_tar:
            image_tar.extractall(extract_path)

        return os.path.join(extract_path, "root.vhd")

    def _read_cloud_properties(self, stemcell_dir: str) -> dict:
        """
        Reads the cloud properties from the stemcell.MF manifest.

        Args:
            stemcell_dir (str): The directory containing the extracted stemcell.MF.

        Returns:
            Dict: The stemcell cloud properties, or an empty dict if unavailable.
        """
        manifest_path: str = os.path.join(stemcell_dir, "stemcell.MF")
        if not os.path.exists(manifest_path):
            self.logger.warning("stemcell.MF not found; proceeding without cloud properties.")
            return {}

        with open(manifest_path) as manifest_file:
            manifest = yaml.safe_load(manifest_file) or {}

        cloud_properties = manifest.get("cloud_properties", {})
        if not isinstance(cloud_properties, dict):
            self.logger.warning("Invalid cloud_properties in stemcell.MF; ignoring.")
            return {}

        return cloud_properties

    def _create_extraction_dir(self) -> str:
        """
        Creates a temporary directory for extracting the stemcell.

        If the mounted directory is available and writable, use it as the
        temporary directory. Otherwise, create a new temporary directory.

        Returns:
            str: The path to the temporary extraction directory.
        """
        mount_dir = self.extraction_directory
        if mount_dir and os.path.exists(mount_dir) and os.access(mount_dir, os.W_OK):
            self.logger.info(f"Using mounted directory {mount_dir} for extraction.")
            return tempfile.mkdtemp(prefix="stemcell-", dir=mount_dir)

        self.logger.warning(f"'{mount_dir}' is not writable or does not exist. Falling back to system temp.")
        return tempfile.mkdtemp(prefix="stemcell-")


class BoshIoJammyMirror(BoshIoStemcellMirror):
    """Mirrors the Ubuntu Jammy (22.04) bosh.io Azure stemcell."""

    stemcell_series = "bosh-azure-hyperv-ubuntu-jammy-go_agent"


class BoshIoNobleMirror(BoshIoStemcellMirror):
    """Mirrors the Ubuntu Noble (24.04) bosh.io Azure stemcell."""

    stemcell_series = "bosh-azure-hyperv-ubuntu-noble"
