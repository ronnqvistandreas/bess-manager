"""Regression guards for the production Dockerfile explicit COPY list."""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DOCKERFILE = REPO_ROOT / "Dockerfile"

# Backend packages copied as directories into /app/ in the production image.
REQUIRED_BACKEND_PACKAGES = ("llm",)


def test_production_dockerfile_copies_backend_packages():
    content = DOCKERFILE.read_text()
    for package in REQUIRED_BACKEND_PACKAGES:
        assert f"COPY backend/{package}/" in content, (
            f"Production Dockerfile must COPY backend/{package}/ into the image "
            f"(see docker-compose.prod-test.yml)."
        )
