from app.config import get_settings


def test_suite_uses_fake_keys_only():
    settings = get_settings()
    checks = {
        "api_key": settings.api_key.get_secret_value().startswith("test-"),
        "groq_api_key": settings.groq_api_key.get_secret_value().startswith("test-"),
        "n8n_writer_password": settings.n8n_writer_password.get_secret_value().startswith("test-"),
        "n8n_webhook_key": settings.n8n_webhook_key.get_secret_value().startswith("test-"),
        "n8n_webhook_url": settings.n8n_webhook_url.get_secret_value().startswith("http://127.0.0.1:9/"),
    }
    assert checks == {name: True for name in checks}