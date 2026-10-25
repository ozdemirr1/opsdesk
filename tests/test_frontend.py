import pytest
from fastapi.testclient import TestClient

from opsdesk.config import Settings
from opsdesk.main import create_app


@pytest.fixture
def frontend_dist(tmp_path):
    directory = tmp_path / "dist"
    assets = directory / "assets"
    assets.mkdir(parents=True)

    (directory / "index.html").write_text(
        '<!doctype html><html><body id="root">OpsDesk</body></html>',
        encoding="utf-8",
    )
    (directory / "favicon.svg").write_text(
        '<svg xmlns="http://www.w3.org/2000/svg"></svg>',
        encoding="utf-8",
    )
    (assets / "app.js").write_text(
        'console.log("frontend-test");',
        encoding="utf-8",
    )
    return directory


def test_frontend_is_optional():
    app = create_app(
        Settings(environment="test", frontend_dist_dir=None),
    )

    with TestClient(app) as client:
        assert client.get("/").status_code == 404
        assert client.get("/health/live").json() == {"status": "ok"}


def test_frontend_serves_build_and_preserves_api(frontend_dist):
    app = create_app(
        Settings(
            environment="test",
            frontend_dist_dir=frontend_dist,
        ),
    )

    with TestClient(app) as client:
        index = client.get("/")
        assert index.status_code == 200
        assert index.headers["content-type"].startswith("text/html")
        assert index.headers["cache-control"] == "no-cache"
        assert "OpsDesk" in index.text

        asset = client.get("/assets/app.js")
        assert asset.status_code == 200
        assert "frontend-test" in asset.text

        assert client.get("/favicon.svg").status_code == 200

        health = client.get("/health/live")
        assert health.status_code == 200
        assert health.json() == {"status": "ok"}

        missing = client.get("/unknown-api-route")
        assert missing.status_code == 404
        assert missing.json()["error"]["code"] == "not_found"

        assert client.get("/assets/missing.js").status_code == 404


@pytest.mark.parametrize(
    "missing",
    ["index.html", "favicon.svg", "assets"],
)
def test_incomplete_frontend_build_is_rejected(frontend_dist, missing):
    target = frontend_dist / missing
    if target.is_dir():
        (target / "app.js").unlink()
        target.rmdir()
    else:
        target.unlink()

    with pytest.raises(RuntimeError, match="Frontend build"):
        create_app(
            Settings(
                environment="test",
                frontend_dist_dir=frontend_dist,
            ),
        )


def test_frontend_does_not_serve_files_outside_assets(frontend_dist):
    marker = "private-test-marker"
    (frontend_dist / "private.txt").write_text(marker, encoding="utf-8")

    app = create_app(
        Settings(
            environment="test",
            frontend_dist_dir=frontend_dist,
        ),
    )

    with TestClient(app) as client:
        for path in ["/private.txt", "/assets/%2e%2e/private.txt"]:
            response = client.get(path)
            assert response.status_code == 404
            assert marker not in response.text
