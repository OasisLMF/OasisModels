"""
Start the OasisPlatform stack with testcontainers' ``DockerCompose``.

Compose files::

    tests/compose/docker-compose.platform.yml     the platform stack + `worker` template (always first)
    tests/compose/docker-compose.test-limits.yml  gunicorn worker count on the server (tests only)
    <Model>/docker/worker-container.yml           one per selected model, extends the `worker` template

Only an env file is generated here: images, API variant, debug flag, the
models root, process limits and a unique compose project name.

Process limits: without them every celery worker and gunicorn starts one process
per CPU, which with all models selected (13 workers on a 16 CPU machine) ran the
host out of memory.  They only apply to stacks started from here; a
`docker compose up` in a model folder keeps the images' defaults.
"""

import logging
import uuid
from pathlib import Path

from testcontainers.compose import DockerCompose

logger = logging.getLogger(__name__)

COMPOSE_DIR = Path(__file__).parent / "compose"
COMPOSE_FILE = COMPOSE_DIR / "docker-compose.platform.yml"
TEST_LIMITS_FILE = COMPOSE_DIR / "docker-compose.test-limits.yml"
# processes per container (celery children / gunicorn workers, plus one parent process each)
WORKER_CONCURRENCY = 4      # model workers: matches the 4 lookup / analysis chunks
MONITOR_CONCURRENCY = 1     # v1/v2 worker monitor
SERVER_WORKERS = 2          # gunicorn on the API server
REPO_ROOT = Path(__file__).parent.parent
API_VERSIONS = ("v1", "v2")
# database profile -> extra env file with its connection settings (postgres uses the compose defaults)
DATABASES = {
    "postgres": None,
    "mysql": COMPOSE_DIR / "mysql.env",
}
# storage between server and workers -> (profile, extra env file); shared-fs is the compose default
STORAGES = {
    "shared-fs": (None, None),
    "s3": ("s3", COMPOSE_DIR / "s3.env"),
}


def worker_compose_file(model_dir: Path) -> Path:
    """Location of a model's worker definition for platform tests."""
    return Path(model_dir) / "docker" / "worker-container.yml"


class PlatformCompose:
    """Wraps ``DockerCompose`` for one API variant and a set of model directories."""

    def __init__(self, server_image, worker_image, model_dirs, api_ver="v2", db="postgres",
                 storage="shared-fs", debug=False, channel_layer=False, work_dir=None):
        if api_ver not in API_VERSIONS:
            raise ValueError(f"api_ver must be one of {API_VERSIONS}, got '{api_ver}'")
        if db not in DATABASES:
            raise ValueError(f"db must be one of {list(DATABASES)}, got '{db}'")
        self.db = db
        if storage not in STORAGES:
            raise ValueError(f"storage must be one of {list(STORAGES)}, got '{storage}'")
        self.storage = storage
        self.server_image = server_image
        self.worker_image = worker_image
        self.api_ver = api_ver
        self.debug = debug
        self.channel_layer = channel_layer
        self.worker_files = [worker_compose_file(Path(d).resolve()) for d in model_dirs]
        missing = [str(f) for f in self.worker_files if not f.is_file()]
        if missing:
            raise FileNotFoundError(f"model worker compose file(s) not found: {missing}")
        self.work_dir = Path(work_dir or Path.cwd() / "platform-stack").resolve()
        self.work_dir.mkdir(parents=True, exist_ok=True)
        self.project = f"oasis-platform-test-{uuid.uuid4().hex[:8]}"
        self.compose = None
        self.api_url = None

    def _write_env_file(self):
        env = {
            "COMPOSE_PROJECT_NAME": self.project,
            "SERVER_IMG": self.server_image,
            "WORKER_IMG": self.worker_image,
            "API_VER": self.api_ver,
            "OASIS_DEBUG": "1" if self.debug else "0",
            "DISABLE_WORKER_WS": "false" if self.channel_layer else "true",
            "OASIS_MODELS_ROOT": str(REPO_ROOT.resolve()),
            "WORKER_CONCURRENCY": WORKER_CONCURRENCY,
            "MONITOR_CONCURRENCY": MONITOR_CONCURRENCY,
            "SERVER_WORKERS": SERVER_WORKERS,
        }
        path = self.work_dir / "platform.env"
        path.write_text("".join(f"{k}={v}\n" for k, v in env.items()))
        return path

    def start(self):
        env_files = [self._write_env_file()]
        profiles = [self.api_ver, self.db]
        if DATABASES[self.db]:
            env_files.append(DATABASES[self.db])
        storage_profile, storage_env = STORAGES[self.storage]
        if storage_profile:
            profiles.append(storage_profile)
        if storage_env:
            env_files.append(storage_env)
        if self.channel_layer:
            profiles.append("channel-layer")

        self.compose = DockerCompose(
            context=COMPOSE_DIR,
            compose_file_name=[str(COMPOSE_FILE), str(TEST_LIMITS_FILE)] + [str(f) for f in self.worker_files],
            env_file=[str(f) for f in env_files],
            profiles=profiles,
            wait=True,          # `up --wait`: blocks until healthchecks pass
        )
        logger.info("starting compose project %s (profiles=%s, workers=%s)",
                    self.project, profiles, [str(f) for f in self.worker_files])
        self.compose.start()

        host, port = self.compose.get_service_host_and_port("server", 8000)
        self.api_url = f"http://{host or 'localhost'}:{port}"
        return self

    def dump_logs(self, out_dir: Path):
        if self.compose is None:
            return
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        try:
            services = [c.Service for c in self.compose.get_containers(include_all=True)]
        except Exception as e:
            logger.warning("could not list compose services: %s", e)
            return
        for service in services:
            try:
                stdout, stderr = self.compose.get_logs(service)
                (out_dir / f"{service}.log").write_text(stdout + stderr)
            except Exception as e:
                logger.warning("could not fetch logs for %s: %s", service, e)

    def stop(self):
        if self.compose is not None:
            self.compose.stop()   # `down --volumes`: removes containers, network and shared-fs volume
            self.compose = None
