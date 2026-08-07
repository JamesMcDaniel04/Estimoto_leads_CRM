"""SPA static serving: real files and client routes work, but unknown
/api/* paths must return a JSON 404 — never index.html with a 200."""

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.main import mount_spa


async def test_spa_serving_and_api_404(tmp_path):
    static = tmp_path / "static"
    (static / "assets").mkdir(parents=True)
    (static / "index.html").write_text("<html>estimoto-app</html>")
    (static / "assets" / "app.js").write_text("console.log('hi')")

    app = FastAPI()
    mount_spa(app, static)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Unknown API path: JSON 404, not the SPA shell.
        resp = await client.get("/api/does-not-exist")
        assert resp.status_code == 404
        assert resp.json()["detail"] == "Not found"

        # Client-side routes fall back to index.html.
        for path in ("/", "/leads", "/board/deep/link"):
            resp = await client.get(path)
            assert resp.status_code == 200
            assert "estimoto-app" in resp.text

        # Real static files are served as-is.
        resp = await client.get("/assets/app.js")
        assert resp.status_code == 200
        assert "console.log" in resp.text
