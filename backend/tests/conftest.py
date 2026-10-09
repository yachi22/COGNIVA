import pytest
from app.services.embeddings import embedding_service, MockEmbeddingProvider
from app.services.llm import llm_service, MockLLMProvider


@pytest.fixture(autouse=True)
def setup_mock_embedding_provider():
    """
    Autouse fixture to ensure all automated test runs use the deterministic
    MockEmbeddingProvider by default, preventing external API calls and
    guaranteeing reliable, fast 1536-dimensional vector generation.
    """
    mock_provider = MockEmbeddingProvider()
    embedding_service.set_provider(mock_provider)
    yield mock_provider
    embedding_service.reset_default_provider()


@pytest.fixture(autouse=True)
def setup_mock_llm_provider():
    """
    Autouse fixture to ensure all automated test runs use the deterministic
    MockLLMProvider by default, preventing external API calls and
    guaranteeing reliable, fast grounded answer synthesis.
    """
    mock_provider = MockLLMProvider()
    llm_service.set_provider(mock_provider)
    yield mock_provider
    llm_service.reset_default_provider()

