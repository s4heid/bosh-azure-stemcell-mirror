import os
import sys
import logging

dir_path = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, dir_path)

import azure.functions as func
from mirror.azure_manager import AzureManager
from mirror.stemcell_mirror import StemcellMirror

subscription_id: str = os.environ["BASM_AZURE_SUBSCRIPTION_ID"]
tenant_id: str = os.environ["BASM_AZURE_TENANT_ID"]
client_id: str = os.environ["BASM_AZURE_CLIENT_ID"]
client_secret: str = os.environ["BASM_AZURE_CLIENT_SECRET"]
resource_group: str = os.environ["BASM_RESOURCE_GROUP"]
location: str = os.environ.get("BASM_REGION", "eastus")

storage_account_name: str = os.environ["BASM_STORAGE_ACCOUNT_NAME"]
gallery_name: str = os.environ.get("BASM_GALLERY_NAME", "bosh-azure-stemcells")
storage_container: str = os.environ.get("BASM_STORAGE_CONTAINER_NAME", "stemcell")
gallery_image_name: str = os.environ.get("BASM_GALLERY_IMAGE_NAME", "Ubuntu-Jammy")
stemcell_series: str = os.environ.get("BASM_STEMCELL_SERIES", "bosh-azure-hyperv-ubuntu-jammy-go_agent")
mounted_dir: str = os.environ.get("BASM_MOUNTED_DIRECTORY", "/mount/stemcellfiles")

app: func.FunctionApp = func.FunctionApp()


@app.timer_trigger(schedule="0 0 7 * * *", arg_name="basmTimer", run_on_startup=True, use_monitor=False)
def bosh_stemcell_mirror(basmTimer: func.TimerRequest) -> None:
    app_logger: logging.Logger = logging.getLogger(__name__)
    app_logger.setLevel(logging.INFO)
    # Azure SDK logs are too verbose, so we'll suppress them.
    az_logger: logging.Logger = logging.getLogger("azure")
    az_logger.setLevel(logging.WARN)
    handler: logging.StreamHandler = logging.StreamHandler(stream=sys.stdout)
    az_logger.addHandler(handler)

    azure_manager: AzureManager = AzureManager(
        client_id=client_id,
        client_secret=client_secret,
        tenant_id=tenant_id,
        subscription_id=subscription_id,
        resource_group=resource_group,
        location=location,
        logger=app_logger
    )
    azure_manager.setup_storage(storage_account_name, storage_container)

    mirror: StemcellMirror = StemcellMirror(azure_manager, mounted_dir, logger=app_logger)
    mirror.run(stemcell_series, gallery_name, gallery_image_name)

    app_logger.info('Completed stemcell mirror run.')
