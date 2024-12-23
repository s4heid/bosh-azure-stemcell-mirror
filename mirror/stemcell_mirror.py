import logging
import os
import shutil
from typing import Optional, List
import requests
import tarfile
import tempfile

from semver.version import Version
from .azure_manager import AzureManager

STEMCELL_API_URL = "https://bosh.io/api/v1/stemcells/"

class StemcellMirror:
    def __init__(
        self,
        azure_manager: AzureManager,
        extraction_directory: str = tempfile.gettempdir(),
        logger: Optional[logging.Logger] = None
    ) -> None:
        self.azure_manager: AzureManager = azure_manager
        self.extraction_directory: str = extraction_directory
        self.logger: logging.Logger = logger or logging.getLogger(__name__)

    def run(
        self,
        stemcell_series: str,
        gallery_name: str,
        gallery_image_name: str
    ) -> None:
        """
        Mirrors the latest stemcell from the given stemcell series to Azure.

        This function checks for the latest stemcell version from the specified
        stemcell series API, downloads it if it's a new version, extracts the
        .vhd file, uploads it to Azure storage, and creates a new gallery image
        version in Azure.

        Args:
            stemcell_series (str): The stemcell series to check for updates.
            gallery_name (str): The name of the Azure Shared Image Gallery.
            gallery_image_name (str): The name of the image definition within the gallery.
        """
        response: requests.Response = requests.get(f"{STEMCELL_API_URL}{stemcell_series}")
        response.raise_for_status()
        stemcells: List[dict] = response.json()

        latest_stemcell: dict = stemcells[0]
        latest_version: str = latest_stemcell.get("version")
        sc_version: Version = Version.parse(latest_version, optional_minor_and_patch=True)
        formatted_latest_version: str = f"{sc_version.major}.{sc_version.minor}.{sc_version.patch}"
        download_url: Optional[str] = latest_stemcell.get("regular", {}).get("url")
        if not download_url:
            raise ValueError("Failed to find download URL for stemcell.")

        version_exists: bool = self.azure_manager.gallery_image_version_exists(
            gallery_name,
            gallery_image_name,
            formatted_latest_version
        )
        if version_exists:
            self.logger.info("No new stemcell to upload.")
            return

        self.logger.info("Checking gallery image definition.")
        self.azure_manager.check_or_create_gallery_image(stemcell_series, gallery_name, gallery_image_name)

        self.logger.info(f"New stemcell version {formatted_latest_version} found. Downloading...")
        extracted_stemcell_dir: str = self._create_extraction_dir()
        try:
            stemcell_path: str = self._download_stemcell(download_url, extracted_stemcell_dir)
            vhd_path: str = self._extract_stemcell(stemcell_path)

            if not os.path.exists(vhd_path):
                raise FileNotFoundError("Failed to find root.vhd in stemcell image.")

            self.logger.info("Uploading .vhd to Azure storage...")
            blob_uri: str = self.azure_manager.upload_vhd(vhd_path)

            self.logger.info(f"Creating new gallery image version {formatted_latest_version}...")
            self.azure_manager.create_gallery_image_version(
                gallery_name,
                gallery_image_name,
                formatted_latest_version,
                blob_uri
            )

            self.logger.info("Completed vhd upload and gallery image version creation.")
        finally:
            self.logger.info(f"Cleaning up temp directory: {extracted_stemcell_dir}")
            shutil.rmtree(extracted_stemcell_dir, ignore_errors=True)

    def _download_stemcell(self, url: str, extract_path: str) -> str:
        """
        Downloads the stemcell archive.

        Args:
            url (str): The URL to download the stemcell from.
            extract_path (str): The directory to download the stemcell.

        Returns:
            str: The path to the extracted VHD.
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
            tar (str): The tarfile to extract the VHD from.

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

    def _create_extraction_dir(self) -> str:
        """
        Creates a temporary directory for extracting the stemcell.

        If the mounted directory is available and writable, use it as the
        temporary directory. Otherwise, create a new temporary directory.

        Args:
            mounted_directory (str): The directory to use if available.

        Returns:
            str: The path to the temporary extraction directory.
        """
        if os.path.exists(self.extraction_directory) and os.access(self.extraction_directory, os.W_OK):
            return tempfile.mkdtemp(prefix="stemcell-", dir=self.extraction_directory)
        raise RuntimeError(f"Failed to create tmp directory at path {self.extraction_directory}")