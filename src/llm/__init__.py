"""
LLM Provider Module for RAG-NetTwin.

This module provides a factory pattern for creating LLM instances from
different providers. It supports multiple LLM backends including Groq,
Google Gemini, and local models via LlamaCpp.

Key Features:
- Factory pattern for LLM instantiation
- Structured output support for parsing
- Provider-specific configuration
- Validation of required API keys
- Extensible to additional providers

Typical Usage:
    from llm import LLMProvider

    # Get a basic LLM instance
    llm = LLMProvider.get_llm(provider="groq", temperature=0.0)

    # Get a structured LLM for parsing
    from parser.intent_parser import StructuredIntent
    parser_llm = LLMProvider.get_structured_llm(schema=StructuredIntent)
"""

import os
from typing import Optional, Type, Any
from langchain_core.language_models import BaseChatModel
from config import settings
from utils import validate_provider_config


class LLMProvider:
    """
    Factory class for creating LLM instances from different providers.

    This class provides a unified interface for obtaining LLM instances
    with consistent configuration. It handles provider-specific setup
    and supports structured output for parsing tasks.

    Supported Providers:
    - Groq: Cloud-based LLM with fast inference
    - Gemini: Google AI LLM via LangChain
    - LlamaCpp: Local LLM running via llama.cpp

    Class Attributes:
        PROVIDER_GROQ: Constant for Groq provider identifier.
        PROVIDER_GEMINI: Constant for Gemini provider identifier.
        PROVIDER_LLAMACPP: Constant for LlamaCpp provider identifier.

    Example:
        >>> llm = LLMProvider.get_llm(provider="groq", temperature=0.0)
        >>> response = llm.invoke("Hello, world!")
    """

    # Provider identifier constants
    PROVIDER_GROQ = "groq"
    PROVIDER_GEMINI = "gemini"
    PROVIDER_LLAMACPP = "llamacpp"

    @staticmethod
    def get_dspy_lm(model: str = None) -> Any:
        """
        Returns a DSPy-compatible language model (Recommendation 3).
        """
        import dspy
        from config import settings
        
        provider = settings.llm_provider
        model = model or settings.groq_model
        api_key = settings.groq_api_key if provider == "groq" else settings.gemini_api_key

        if provider == "groq":
            return dspy.Groq(model=model, api_key=api_key)
        elif provider == "gemini":
            return dspy.Google(model=model, api_key=api_key)
        else:
            raise ValueError(f"DSPy currently doesn't support provider: {provider}")

    @staticmethod
    def get_llm(
        provider: Optional[str] = None,
        model: Optional[str] = None,
        temperature: float = 0.0,
        api_key: Optional[str] = None,
    ) -> "BaseChatModel":
        """
        Get an LLM instance for the specified provider.

        This factory method creates and returns an LLM instance based
        on the provider. It uses settings defaults if not specified.

        Args:
            provider: LLM provider name. If None, uses settings.llm_provider.
                Options: "groq", "gemini", "llamacpp".
            model: Optional model name override. If None, uses provider default.
            temperature: LLM temperature (0.0 = deterministic, 1.0 = creative).
                Default is 0.0 for consistent, reproducible outputs.
            api_key: Optional API key override. If None, uses settings.

        Returns:
            BaseChatModel instance for the specified provider.

        Raises:
            ValueError: If provider is not supported.

        Example:
            >>> # Use defaults from settings
            >>> llm = LLMProvider.get_llm()
            >>>
            >>> # Use specific model
            >>> llm = LLMProvider.get_llm(model="llama-3.1-70b-versatile")
        """
        provider = provider or settings.llm_provider

        if provider == LLMProvider.PROVIDER_GROQ:
            return LLMProvider._get_groq_llm(model, temperature, api_key)
        elif provider == LLMProvider.PROVIDER_GEMINI:
            return LLMProvider._get_gemini_llm(model, temperature, api_key)
        elif provider == LLMProvider.PROVIDER_LLAMACPP:
            return LLMProvider._get_llamacpp_llm(model, temperature)
        else:
            raise ValueError(
                f"Unsupported LLM provider: '{provider}'. "
                f"Supported providers: {LLMProvider.PROVIDER_GROQ}, {LLMProvider.PROVIDER_GEMINI}, {LLMProvider.PROVIDER_LLAMACPP}"
            )

    @staticmethod
    def _get_groq_llm(
        model: Optional[str] = None,
        temperature: float = 0.0,
        api_key: Optional[str] = None,
    ) -> BaseChatModel:
        """
        Create a Groq LLM instance.

        Args:
            model: Model name (default: settings.groq_model).
            temperature: Sampling temperature (default: 0.0).
            api_key: API key override (default: settings.groq_api_key).

        Returns:
            ChatGroq instance.
        """
        try:
            from langchain_groq import ChatGroq
        except ImportError:
            raise ImportError("pip install langchain-groq")

        api_key = api_key or settings.groq_api_key
        model = model or settings.groq_model
        return ChatGroq(model=model, temperature=temperature, api_key=api_key)

    @staticmethod
    def _get_gemini_llm(
        model: Optional[str] = None,
        temperature: float = 0.0,
        api_key: Optional[str] = None,
    ) -> BaseChatModel:
        """
        Create a Google Gemini LLM instance.

        Args:
            model: Model name (default: settings.gemini_model).
            temperature: Sampling temperature (default: 0.0).
            api_key: API key override (default: settings.gemini_api_key).

        Returns:
            ChatGoogleGenerativeAI instance.
        """
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI
        except ImportError:
            raise ImportError("pip install langchain-google-genai")

        api_key = api_key or settings.gemini_api_key
        model = model or settings.gemini_model
        return ChatGoogleGenerativeAI(
            model=model, temperature=temperature, api_key=api_key
        )

    @staticmethod
    def _get_llamacpp_llm(
        model: Optional[str] = None,
        temperature: float = 0.0,
    ) -> BaseChatModel:
        """
        Create a LlamaCpp local LLM instance.

        Args:
            model: Path to model file (default: settings.llama_cpp_model_path).
            temperature: Sampling temperature (default: 0.0).

        Returns:
            ChatLlamaCpp instance.

        Note:
            Requires llama-cpp-python and a compatible model file.
        """
        try:
            from langchain_community.chat_models import ChatLlamaCpp
        except ImportError:
            raise ImportError("pip install langchain-community llama-cpp-python")

        model_path = model or settings.llama_cpp_model_path
        return ChatLlamaCpp(
            model_path=model_path,
            temperature=temperature,
            n_ctx=settings.llama_cpp_n_ctx,
            n_gpu_layers=settings.llama_cpp_n_gpu_layers,
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

        This method wraps an LLM with structured output capability,
        enabling it to return Pydantic models or JSON schemas directly.
        This is essential for tasks like intent parsing where the
        output needs to be validated.

        Args:
            schema: Pydantic model class or JSON schema to output.
            provider: Optional provider override.
            model: Optional model name override.
            temperature: Sampling temperature (default: 0.0).
            api_key: Optional API key override.

        Returns:
            LLM instance with structured output capability.

        Example:
            >>> from parser.intent_parser import StructuredIntent
            >>> parser_llm = LLMProvider.get_structured_llm(schema=StructuredIntent)
            >>> result = parser_llm.invoke("Configure OSPF on Router-A")
            >>> type(result)
            <class 'StructuredIntent'>
        """
        llm = LLMProvider.get_llm(provider, model, temperature, api_key)
        provider = provider or settings.llm_provider

        # Different providers have different methods for structured output
        if provider == LLMProvider.PROVIDER_GROQ:
            return llm.with_structured_output(schema)
        elif provider == LLMProvider.PROVIDER_GEMINI:
            try:
                return llm.with_structured_output(schema)
            except AttributeError:
                # Fallback for older versions
                return llm.bind(response_format=schema)
        else:
            return llm.with_structured_output(schema)

    @staticmethod
    def validate_provider_config(provider: Optional[str] = None) -> bool:
        """
        Validate that the provider configuration is correct.

        This method uses centralized validation logic from utils.py
        to check that required API keys are present for the provider.

        Args:
            provider: Optional provider to validate. If None, uses settings.

        Returns:
            True if configuration is valid.

        Raises:
            ValueError: If required configuration is missing.
        """
        provider = provider or settings.llm_provider
        validate_provider_config(provider, settings.model_dump())
        return True

    @staticmethod
    def list_supported_providers() -> list:
        """
        Return list of supported provider names.

        Returns:
            List of provider identifier strings.
        """
        return [
            LLMProvider.PROVIDER_GROQ,
            LLMProvider.PROVIDER_GEMINI,
            LLMProvider.PROVIDER_LLAMACPP,
        ]

    @staticmethod
    def get_default_model(provider: Optional[str] = None) -> str:
        """
        Get the default model for a provider.

        Args:
            provider: Provider to get default for. If None, uses settings.

        Returns:
            Default model name for the provider.

        Raises:
            ValueError: If provider is unknown.
        """
        provider = provider or settings.llm_provider
        if provider == LLMProvider.PROVIDER_GROQ:
            return settings.groq_model
        elif provider == LLMProvider.PROVIDER_GEMINI:
            return settings.gemini_model
        elif provider == LLMProvider.PROVIDER_LLAMACPP:
            return settings.llama_cpp_model_path
        else:
            raise ValueError(f"Unknown provider: {provider}")


# Convenience functions for common use cases


def get_llm(**kwargs) -> BaseChatModel:
    """
    Convenience function to get an LLM with default settings.

    Args:
        **kwargs: Arguments passed to LLMProvider.get_llm().

    Returns:
        LLM instance.

    Example:
        >>> llm = get_llm(temperature=0.5)
    """
    return LLMProvider.get_llm(**kwargs)


def get_structured_llm(schema: Type[Any], **kwargs) -> BaseChatModel:
    """
    Convenience function to get a structured LLM.

    Args:
        schema: Pydantic model class for structured output.
        **kwargs: Arguments passed to LLMProvider.get_structured_llm().

    Returns:
        Structured LLM instance.

    Example:
        >>> from parser.intent_parser import StructuredIntent
        >>> parser = get_structured_llm(StructuredIntent)
    """
    return LLMProvider.get_structured_llm(schema, **kwargs)
