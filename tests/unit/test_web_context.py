"""Unit tests for app/services/web_context.py."""

from unittest.mock import MagicMock, patch

from app.services import web_context


def test_fetch_real_world_problems_empty_intent():
    assert web_context.fetch_real_world_problems("") == ""
    assert web_context.fetch_real_world_problems("   ") == ""


@patch("app.services.web_context.settings")
@patch("app.services.web_context.chat_model")
def test_fetch_via_sonar_uses_settings_search_model(mock_chat_model, mock_settings):
    mock_settings.api_key = "test-key"
    mock_settings.search_model = "custom/search-model"
    mock_response = MagicMock()
    mock_response.content = "Problem A"
    mock_chat_model.return_value.invoke.return_value = mock_response

    web_context.fetch_real_world_problems("payments")

    mock_chat_model.assert_called_once_with("custom/search-model")


@patch("app.services.web_context.settings")
@patch("app.services.web_context.chat_model")
@patch("app.services.web_context.web_search_project_ideas")
def test_fetch_falls_back_to_tavily_when_sonar_fails(mock_tavily, mock_chat_model, mock_settings):
    mock_settings.api_key = "test-key"
    mock_settings.tavily_api_key = "tavily-key"
    mock_chat_model.return_value.invoke.side_effect = RuntimeError("sonar down")
    mock_tavily.invoke.return_value = "tavily context"

    result = web_context.fetch_real_world_problems("fintech APIs")

    assert result == "tavily context"
    mock_tavily.invoke.assert_called_once()


@patch("app.services.web_context.settings")
@patch("app.services.web_context.chat_model")
def test_fetch_returns_empty_when_sonar_fails_and_no_tavily(mock_chat_model, mock_settings):
    mock_settings.api_key = "test-key"
    mock_settings.tavily_api_key = None
    mock_chat_model.return_value.invoke.side_effect = RuntimeError("sonar down")

    assert web_context.fetch_real_world_problems("rust wasm") == ""
