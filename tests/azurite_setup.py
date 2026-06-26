import os
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent


def _seed_azurite(conn_str):
    from azure.storage.blob import BlobServiceClient
    client = BlobServiceClient.from_connection_string(conn_str)
    try:
        client.create_container("data")
    except Exception:
        pass
    for src, prefix in [
        (REPO_ROOT / "PiWind" / "model_data", "OasisPiWind/model_data/PiWind"),
        (REPO_ROOT / "PiWind" / "keys_data",  "OasisPiWind/keys_data/PiWind"),
    ]:
        for f in Path(src).rglob("*"):
            if f.is_file():
                blob = f"{prefix}/{f.relative_to(src)}"
                client.get_blob_client("data", blob).upload_blob(
                    f.read_bytes(), overwrite=True
                )


@pytest.fixture(scope="session")
def azurite_service():
    from testcontainers.core.container import DockerContainer
    from testcontainers.core.waiting_utils import wait_for_logs

    with DockerContainer("mcr.microsoft.com/azure-storage/azurite") \
            .with_command("azurite-blob --blobHost 0.0.0.0") \
            .with_exposed_ports(10000) as container:
        wait_for_logs(container, "Azurite Blob service is successfully listening")
        host = container.get_container_host_ip()
        port = container.get_exposed_port(10000)
        conn_str = (
            f"DefaultEndpointsProtocol=http;"
            f"AccountName=devstoreaccount1;"
            f"AccountKey=Eby8vdM02xNOcqFlqUwJPLlmEtlCDXJ1OtO+kSHAHNaIQgFQAAFdtE0jDdqoiQqT6i0xqQpqHfNKOEFAAAABQk=;"
            f"BlobEndpoint=http://{host}:{port}/devstoreaccount1;"
        )
        _seed_azurite(conn_str)
        os.environ["AZURE_STORAGE_CONNECTION_STRING"] = conn_str
        yield
        os.environ.pop("AZURE_STORAGE_CONNECTION_STRING", None)
