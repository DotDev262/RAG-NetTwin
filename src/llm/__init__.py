"""
LLM Provider module for RAG-NetTwin
Supports multiple LLM providers: Groq, Gemini, and extensible to others
"""

import os
from typing import Optional, Type, Any
from langchain_core.language_models import BaseChatModel
from config import settings
from utils import validate_provider_config


class LLMProvider:
    """
    Factory class for creating LLM instances from different providers.
    Supports Groq and Gemini out of the box.
    """

    PROVIDER_GROQ = "groq"
    PROVIDER_GEMINI = "gemini"
    PROVIDER_LLAMACPP = "llamacpp"

    @staticmethod
    def get_llm(
        provider: Optional[str] = None,
        model: Optional[str] = None,
        temperature: float = 0.0,
        api_key: Optional[str] = None,
    ) -> "BaseChatModel":
        """
        Get an LLM instance for the specified provider.
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
        """Create a Groq LLM instance."""
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
        """Create a Gemini LLM instance."""
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
        """Create a LlamaCpp LLM instance."""
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
        """
        llm = LLMProvider.get_llm(provider, model, temperature, api_key)
        provider = provider or settings.llm_provider

        if provider == LLMProvider.PROVIDER_GROQ:
            return llm.with_structured_output(schema)
        elif provider == LLMProvider.PROVIDER_GEMINI:
            try:
                return llm.with_structured_output(schema)
            except AttributeError:
                return llm.bind(response_format=schema)
        else:
            return llm.with_structured_output(schema)

    @staticmethod
    def validate_provider_config(provider: Optional[str] = None) -> bool:
        """
        Validate that the provider configuration is correct.
        Uses centralized logic in utils.py.
        """
        provider = provider or settings.llm_provider
        validate_provider_config(provider, settings.model_dump())
        return True

    @staticmethod
    def list_supported_providers() -> list:
        """Return list of supported provider names."""
        return [
            LLMProvider.PROVIDER_GROQ,
            LLMProvider.PROVIDER_GEMINI,
            LLMProvider.PROVIDER_LLAMACPP,
        ]

    @staticmethod
    def get_default_model(provider: Optional[str] = None) -> str:
        """Get the default model for a provider."""
        provider = provider or settings.llm_provider
        if provider == LLMProvider.PROVIDER_GROQ:
            return settings.groq_model
        elif provider == LLMProvider.PROVIDER_GEMINI:
            return settings.gemini_model
        elif provider == LLMProvider.PROVIDER_LLAMACPP:
            return settings.llama_cpp_model_path
        else:
            raise ValueError(f"Unknown provider: {provider}")


# Convenience functions
def get_llm(**kwargs) -> BaseChatModel:
    return LLMProvider.get_llm(**kwargs)


def get_structured_llm(schema: Type[Any], **kwargs) -> BaseChatModel:
    return LLMProvider.get_structured_llm(schema, **kwargs)
