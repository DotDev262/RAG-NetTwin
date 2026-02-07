"""
LLM Provider module for RAG-NetTwin
Supports multiple LLM providers: Groq, Gemini, and extensible to others
"""

import os
from typing import Optional, Type, Any
from langchain_core.language_models import BaseChatModel
from config import settings


class LLMProvider:
    """
    Factory class for creating LLM instances from different providers.
    Supports Groq and Gemini out of the box.
    """

    PROVIDER_GROQ = "groq"
    PROVIDER_GEMINI = "gemini"

    @staticmethod
    def get_llm(
        provider: Optional[str] = None,
        model: Optional[str] = None,
        temperature: float = 0.0,
        api_key: Optional[str] = None,
    ) -> "BaseChatModel":
        """
        Get an LLM instance for the specified provider.

        Args:
            provider: LLM provider name ('groq', 'gemini', or None for default from settings)
            model: Model name (e.g., 'llama-3.3-70b-versatile', 'gemini-1.5-flash')
            temperature: Sampling temperature (0.0 to 1.0)
            api_key: API key (optional, will use env var if not provided)

        Returns:
            BaseChatModel instance configured for the provider

        Raises:
            ValueError: If provider is not supported or API key is missing
        """
        provider = provider or settings.llm_provider

        if provider == LLMProvider.PROVIDER_GROQ:
            return LLMProvider._get_groq_llm(model, temperature, api_key)
        elif provider == LLMProvider.PROVIDER_GEMINI:
            return LLMProvider._get_gemini_llm(model, temperature, api_key)
        else:
            raise ValueError(
                f"Unsupported LLM provider: '{provider}'. "
                f"Supported providers: {LLMProvider.PROVIDER_GROQ}, {LLMProvider.PROVIDER_GEMINI}"
            )

    @staticmethod
    def _get_groq_llm(
        model: Optional[str] = None,
        temperature: float = 0.0,
        api_key: Optional[str] = None,
    ) -> BaseChatModel:
        """Create a Groq LLM instance."""
        try:
            from langchain_groq import ChatGroq
        except ImportError:
            raise ImportError(
                "langchain-groq is not installed. "
                "Install it with: pip install langchain-groq"
            )

        api_key = api_key or settings.groq_api_key
        if not api_key or api_key == "your_api_key_here":
            raise ValueError(
                "GROQ_API_KEY not found in settings or environment. "
                "Please set GROQ_API_KEY in your .env file."
            )

        model = model or settings.groq_model

        return ChatGroq(model=model, temperature=temperature, api_key=api_key)

    @staticmethod
    def _get_gemini_llm(
        model: Optional[str] = None,
        temperature: float = 0.0,
        api_key: Optional[str] = None,
    ) -> BaseChatModel:
        """Create a Gemini LLM instance."""
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI
        except ImportError:
            raise ImportError(
                "langchain-google-genai is not installed. "
                "Install it with: pip install langchain-google-genai"
            )

        api_key = api_key or settings.gemini_api_key
        if not api_key or api_key == "your_api_key_here":
            raise ValueError(
                "GEMINI_API_KEY not found in settings or environment. "
                "Please set GEMINI_API_KEY in your .env file."
            )

        model = model or settings.gemini_model

        return ChatGoogleGenerativeAI(
            model=model, temperature=temperature, api_key=api_key
        )

    @staticmethod
    def get_structured_llm(
        schema: Type[Any],
        provider: Optional[str] = None,
        model: Optional[str] = None,
        temperature: float = 0.0,
        api_key: Optional[str] = None,
    ) -> BaseChatModel:
        """
        Get an LLM with structured output support.

        Args:
            schema: Pydantic model class defining the output structure
            provider: LLM provider name
            model: Model name
            temperature: Sampling temperature
            api_key: API key (optional)

        Returns:
            LLM instance configured for structured output
        """
        llm = LLMProvider.get_llm(provider, model, temperature, api_key)

        provider = provider or settings.llm_provider

        if provider == LLMProvider.PROVIDER_GROQ:
            # Groq uses with_structured_output
            return llm.with_structured_output(schema)
        elif provider == LLMProvider.PROVIDER_GEMINI:
            # Gemini also uses with_structured_output in newer versions
            # Fallback to bind if needed
            try:
                return llm.with_structured_output(schema)
            except AttributeError:
                # Fallback for older versions
                return llm.bind(response_format=schema)
        else:
            # Default to standard structured output
            return llm.with_structured_output(schema)

    @staticmethod
    def validate_provider_config(provider: Optional[str] = None) -> bool:
        """
        Validate that the provider configuration is correct.

        Args:
            provider: Provider to validate (uses settings.llm_provider if None)

        Returns:
            True if configuration is valid

        Raises:
            ValueError: If configuration is invalid
        """
        provider = provider or settings.llm_provider

        if provider == LLMProvider.PROVIDER_GROQ:
            if (
                not settings.groq_api_key
                or settings.groq_api_key == "your_api_key_here"
            ):
                raise ValueError(
                    f"GROQ_API_KEY is required when using provider '{provider}'. "
                    f"Please set GROQ_API_KEY in your .env file."
                )
        elif provider == LLMProvider.PROVIDER_GEMINI:
            if (
                not settings.gemini_api_key
                or settings.gemini_api_key == "your_api_key_here"
            ):
                raise ValueError(
                    f"GEMINI_API_KEY is required when using provider '{provider}'. "
                    f"Please set GEMINI_API_KEY in your .env file."
                )
        else:
            raise ValueError(
                f"Unsupported LLM provider: '{provider}'. "
                f"Supported: {LLMProvider.PROVIDER_GROQ}, {LLMProvider.PROVIDER_GEMINI}"
            )

        return True

    @staticmethod
    def list_supported_providers() -> list:
        """Return list of supported provider names."""
        return [LLMProvider.PROVIDER_GROQ, LLMProvider.PROVIDER_GEMINI]

    @staticmethod
    def get_default_model(provider: Optional[str] = None) -> str:
        """Get the default model for a provider."""
        provider = provider or settings.llm_provider

        if provider == LLMProvider.PROVIDER_GROQ:
            return settings.groq_model
        elif provider == LLMProvider.PROVIDER_GEMINI:
            return settings.gemini_model
        else:
            raise ValueError(f"Unknown provider: {provider}")


# Convenience function for quick LLM instantiation
def get_llm(**kwargs) -> BaseChatModel:
    """Convenience wrapper for LLMProvider.get_llm()"""
    return LLMProvider.get_llm(**kwargs)


def get_structured_llm(schema: Type[Any], **kwargs) -> BaseChatModel:
    """Convenience wrapper for LLMProvider.get_structured_llm()"""
    return LLMProvider.get_structured_llm(schema, **kwargs)
