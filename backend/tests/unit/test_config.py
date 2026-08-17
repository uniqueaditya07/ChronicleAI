from app.config import Settings, get_settings


def test_settings_load_defaults():
    settings = get_settings()
    assert settings.APP_NAME == "ChronicleAI API"
    assert settings.APP_VERSION == "0.1.0"
    assert settings.ENVIRONMENT in ["development", "testing", "production"]
    assert settings.API_PORT == 8000
    assert "http://localhost:5173" in settings.CORS_ORIGINS
    assert settings.DATABASE_URL.startswith("sqlite")
    assert settings.DATA_DIR.exists()
