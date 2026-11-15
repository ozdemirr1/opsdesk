import importlib.util
from pathlib import Path

import pytest

path = Path(__file__).resolve().parents[1] / "scripts/compose/acceptance.py"
spec = importlib.util.spec_from_file_location("compose_acceptance", path)
acceptance = importlib.util.module_from_spec(spec)
spec.loader.exec_module(acceptance)


@pytest.mark.parametrize(
    "binding", ["0.0.0.0:8089", "example.com:8089", "127.0.0.1:0", "127.0.0.1:65536"]
)
def test_acceptance_rejects_nonlocal_or_invalid_binding(binding):
    with pytest.raises(RuntimeError):
        acceptance.local_origin(binding)


def test_acceptance_accepts_loopback():
    assert acceptance.local_origin("127.0.0.1:8089") == "http://127.0.0.1:8089"


def test_assets_ignore_external_urls_and_reject_traversal():
    assets = acceptance.Assets()
    assets.feed('<script src="https://example.com/external.js"></script>')
    assert not assets.paths
    with pytest.raises(RuntimeError):
        assets.feed('<script src="/assets/../private"></script>')


def test_redirects_are_not_followed():
    assert (
        acceptance.NoRedirect().redirect_request(
            None, None, 302, None, {}, "https://example.com"
        )
        is None
    )
