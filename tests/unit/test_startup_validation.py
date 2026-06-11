from unittest.mock import patch

import pytest

from app import create_app
from app.startup_validation import StartupValidationError, validate_required_env_vars


def test_validate_required_env_vars_returns_values_for_required_names():
    env_values = validate_required_env_vars(
        ("FIRST_REQUIRED_ENV_VAR", "SECOND_REQUIRED_ENV_VAR"),
        {
            "FIRST_REQUIRED_ENV_VAR": "first-value",
            "SECOND_REQUIRED_ENV_VAR": "second-value",
            "UNRELATED_ENV_VAR": "unrelated-value",
        },
    )

    assert env_values == {
        "FIRST_REQUIRED_ENV_VAR": "first-value",
        "SECOND_REQUIRED_ENV_VAR": "second-value",
    }


def test_validate_required_env_vars_rejects_missing_and_blank_values():
    with pytest.raises(StartupValidationError) as exc_info:
        validate_required_env_vars(
            (
                "PRESENT_ENV_VAR",
                "MISSING_ENV_VAR",
                "BLANK_ENV_VAR",
                "NULL_PLACEHOLDER_ENV_VAR",
                "NONE_PLACEHOLDER_ENV_VAR",
                "NIL_PLACEHOLDER_ENV_VAR",
                "UNDEFINED_PLACEHOLDER_ENV_VAR",
            ),
            {
                "PRESENT_ENV_VAR": "present-value",
                "BLANK_ENV_VAR": "   ",
                "NULL_PLACEHOLDER_ENV_VAR": "null",
                "NONE_PLACEHOLDER_ENV_VAR": " None ",
                "NIL_PLACEHOLDER_ENV_VAR": "NIL",
                "UNDEFINED_PLACEHOLDER_ENV_VAR": "undefined",
            },
        )

    assert str(exc_info.value) == (
        "Missing required environment variable(s): MISSING_ENV_VAR, BLANK_ENV_VAR, "
        "NULL_PLACEHOLDER_ENV_VAR, NONE_PLACEHOLDER_ENV_VAR, "
        "NIL_PLACEHOLDER_ENV_VAR, UNDEFINED_PLACEHOLDER_ENV_VAR"
    )


def test_create_app_requires_flask_secret_key_and_database_uri():
    with (
        patch.dict("os.environ", {}, clear=True),
        pytest.raises(StartupValidationError) as exc_info,
    ):
        create_app()

    assert str(exc_info.value) == (
        "Missing required environment variable(s): FLASK_SECRET_KEY, DATABASE_URI"
    )


def test_create_app_uses_validated_config_values():
    with patch.dict(
        "os.environ",
        {
            "FLASK_SECRET_KEY": "validated-secret-key",
            "DATABASE_URI": "postgresql+psycopg://user:pass@localhost:5432/mydb",
        },
    ):
        app = create_app()

    assert app.config["SECRET_KEY"] == "validated-secret-key"
    assert (
        app.config["SQLALCHEMY_DATABASE_URI"]
        == "postgresql+psycopg://user:pass@localhost:5432/mydb"
    )
