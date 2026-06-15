import os
import time
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent


def pytest_collection_modifyitems(config, items):
    dc_files = config.getoption("--docker-compose", default=[]) or []
    if any("azurite" in str(f) for f in dc_files):
        for item in items:
            if "PiWindAzure" in item.nodeid:
                item.own_markers = [m for m in item.own_markers if m.name != "skip"]


def _wait_for_azurite(hostname, port, timeout=30):
    import urllib.request
    url = f"http://{hostname}:{port}/devstoreaccount1"
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            urllib.request.urlopen(url, timeout=2)
            return
        except Exception:
            time.sleep(1)
    raise RuntimeError(f"Azurite did not become ready at {url} within {timeout}s")


def _seed_azurite(conn_str):
    from azure.storage.blob import BlobServiceClient
    client = BlobServiceClient.from_connection_string(conn_str)
    try:
        client.create_container("data")
    except Exception:
        pass  # container may already exist if --use-running-containers
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
def azurite_service(session_scoped_container_getter):
    try:
        net = session_scoped_container_getter.get("azurite").network_info[0]
    except Exception:
        yield
        return

    _wait_for_azurite(net.hostname, net.host_port)
    conn_str = (
        f"DefaultEndpointsProtocol=http;"
        f"AccountName=devstoreaccount1;"
        f"AccountKey=Eby8vdM02xNOcqFlqUwJPLlmEtlCDXJ1OtO+kSHAHNaIQgFQAAFdtE0jDdqoiQqT6i0xqQpqHfNKOEFAAAABQk=;"
        f"BlobEndpoint=http://{net.hostname}:{net.host_port}/devstoreaccount1;"
    )
    _seed_azurite(conn_str)
    os.environ["AZURE_STORAGE_CONNECTION_STRING"] = conn_str
    yield
    os.environ.pop("AZURE_STORAGE_CONNECTION_STRING", None)
