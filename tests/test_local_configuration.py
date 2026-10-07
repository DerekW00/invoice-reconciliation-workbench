def test_same_host_demo_has_product_cookie_identity():
    from django.conf import settings

    assert settings.SESSION_COOKIE_NAME == "invoice_recon_session"
    assert settings.CSRF_COOKIE_NAME == "invoice_recon_csrf"
    assert settings.SESSION_COOKIE_DOMAIN is None
    assert settings.CSRF_COOKIE_DOMAIN is None


def test_browser_artifact_default_is_owned_temp(monkeypatch, tmp_path):
    import tempfile
    from tests.browser_artifacts import evidence_directory

    monkeypatch.delenv("BROWSER_EVIDENCE_DIR", raising=False)
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))
    path = evidence_directory()
    assert path.parent == tmp_path
    (path / "artifact.txt").write_text("portable")


def test_browser_artifact_override_creates_directory(monkeypatch, tmp_path):
    from tests.browser_artifacts import evidence_directory

    target = tmp_path / "nested" / "evidence"
    monkeypatch.setenv("BROWSER_EVIDENCE_DIR", str(target))
    assert evidence_directory() == target
    assert target.is_dir()
