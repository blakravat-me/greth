from pathlib import Path

from greth.runtime.docker import COMPOSE_FILE, PROJECT_ROOT


def test_runtime_paths_resolve_from_repository_root():
    repository_root = Path(__file__).resolve().parents[1]

    assert PROJECT_ROOT == repository_root
    assert COMPOSE_FILE == repository_root / "docker-compose.yml"
