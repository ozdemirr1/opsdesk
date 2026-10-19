from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles


def mount_frontend(app: FastAPI, directory: Path | None) -> None:
    if directory is None:
        return

    directory = directory.resolve()
    index_path = directory / "index.html"
    favicon_path = directory / "favicon.svg"
    assets_path = directory / "assets"

    if (
        not index_path.is_file()
        or not favicon_path.is_file()
        or not assets_path.is_dir()
    ):
        raise RuntimeError("Frontend build is missing or incomplete.")

    @app.get("/", include_in_schema=False)
    def frontend_index() -> FileResponse:
        return FileResponse(
            index_path,
            headers={"Cache-Control": "no-cache"},
        )

    @app.get("/favicon.svg", include_in_schema=False)
    def frontend_favicon() -> FileResponse:
        return FileResponse(favicon_path)

    app.mount(
        "/assets",
        StaticFiles(directory=assets_path, follow_symlink=False),
        name="frontend-assets",
    )
