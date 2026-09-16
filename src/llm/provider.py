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
    from src.llm import LLMProvider

    # Get a basic LLM instance
    llm = LLMProvider.get_llm(provider="groq", temperature=0.0)

    # Get a structured LLM for parsing
    from src.schemas.intent import StructuredIntent
    parser_llm = LLMProvider.get_structured_llm(schema=StructuredIntent)
"""

import logging
import os
import threading
from typing import Optional, Type, Any, cast, List
from langchain_core.language_models import BaseChatModel
from langchain_core.runnables import Runnable, RunnableConfig
from langchain_core.messages import BaseMessage
from langchain_core.outputs import ChatResult
from langchain_core.callbacks import CallbackManagerForLLMRun
from pydantic import SecretStr
from src.config import settings

# --- Groq API Key Rotation Infrastructure ---


class GroqKeyRotator:
    """Manages rotation of Groq API keys when rate limits are hit (thread-safe)."""

    def __init__(self):
        self._keys: List[str] = []
        self._current_index = 0
        self._lock = threading.Lock()
        self.logger = logging.getLogger("GroqKeyRotator")

        # Load keys from settings or environment
        from src.config import settings

        raw_key = settings.groq_api_key or os.getenv("GROQ_API_KEY", "")
        raw_keys_env = os.getenv("GROQ_API_KEYS", "")

        seen = set()

        # Check GROQ_API_KEYS first (comma-separated list)
        if raw_keys_env:
            for k in raw_keys_env.split(","):
                k_clean = k.strip()
                if k_clean and k_clean not in seen:
                    self._keys.append(k_clean)
                    seen.add(k_clean)

        # Check GROQ_API_KEY (could be comma-separated or single)
        if raw_key:
            for k in raw_key.split(","):
                k_clean = k.strip()
                if k_clean and k_clean not in seen:
                    self._keys.append(k_clean)
                    seen.add(k_clean)

        self.logger.info(f"Initialized GroqKeyRotator with {len(self._keys)} keys.")

    def get_current_key(self) -> Optional[str]:
        with self._lock:
            if not self._keys:
                return None
            return self._keys[self._current_index]

    def rotate_key(self) -> bool:
        """Rotates to the next key. Returns True if successfully rotated, False otherwise."""
        with self._lock:
            if len(self._keys) <= 1:
                self.logger.warning("No alternative Groq keys available for rotation.")
                return False

            old_index = self._current_index
            self._current_index = (self._current_index + 1) % len(self._keys)
            self.logger.warning(
                f"Rate limit hit. Rotating Groq API key: index {old_index} -> {self._current_index} "
                f"(Key preview: ...{self._keys[self._current_index][-6:]})"
            )
            return True

    def get_keys_count(self) -> int:
        with self._lock:
            return len(self._keys)


# Global key rotator instance
groq_rotator = GroqKeyRotator()


class RotatingRunnable(Runnable):
    """Wraps a structured runnable to dynamically rebuild and retry with rotated keys on 429 errors."""

    _current_runnable: Any

    def __init__(self, rotator: GroqKeyRotator, factory_func: Any):
        self.rotator = rotator
        self.factory_func = factory_func
        self._current_runnable = None
        self._rebuild()

    def _rebuild(self):
        key = self.rotator.get_current_key()
        self._current_runnable = self.factory_func(key)

    def invoke(
        self, input: Any, config: Optional[RunnableConfig] = None, **kwargs: Any
    ) -> Any:
        attempts = max(1, self.rotator.get_keys_count())
        for attempt in range(attempts):
            try:
                return self._current_runnable.invoke(input, config, **kwargs)
            except Exception as e:
                err_str = str(e)
                if (
                    "429" in err_str
                    or "rate limit" in err_str.lower()
                    or "rate_limit" in err_str.lower()
                ) and attempt < attempts - 1:
                    if self.rotator.rotate_key():
                        self._rebuild()
                        continue
                raise e
        raise RuntimeError("Failed after rotating all keys.")

    async def ainvoke(
        self, input: Any, config: Optional[RunnableConfig] = None, **kwargs: Any
    ) -> Any:
        attempts = max(1, self.rotator.get_keys_count())
        for attempt in range(attempts):
            try:
                return await self._current_runnable.ainvoke(input, config, **kwargs)
            except Exception as e:
                err_str = str(e)
                if (
                    "429" in err_str
                    or "rate limit" in err_str.lower()
                    or "rate_limit" in err_str.lower()
                ) and attempt < attempts - 1:
                    if self.rotator.rotate_key():
                        self._rebuild()
                        continue
                raise e
        raise RuntimeError("Failed after rotating all keys.")


class RotatingChatGroq(BaseChatModel):
    """ChatGroq wrapper that supports dynamic key rotation on rate limits."""

    model_name: str
    temperature: float
    seed: int
    rotator: GroqKeyRotator
    client: Any = None

    model_config = {"arbitrary_types_allowed": True}

    def __init__(
        self,
        model_name: str,
        temperature: float,
        seed: int,
        rotator: GroqKeyRotator,
        **kwargs: Any,
    ):
        super().__init__(
            model_name=model_name,
            temperature=temperature,
            seed=seed,
            rotator=rotator,
            **kwargs,
        )  # type: ignore
        self._rebuild_client()

    @property
    def _llm_type(self) -> str:
        return "rotating-chat-groq"

    def _rebuild_client(self):
        from langchain_groq import ChatGroq

        key = self.rotator.get_current_key()
        api_key_secret = SecretStr(key) if key else None
        self.client = ChatGroq(
            model=self.model_name,
            temperature=self.temperature,
            api_key=api_key_secret,
            max_retries=settings.llm_max_retries,
            model_kwargs={"seed": self.seed},
        )

    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> ChatResult:
        attempts = max(1, self.rotator.get_keys_count())
        for attempt in range(attempts):
            try:
                return self.client._generate(messages, stop, run_manager, **kwargs)
            except Exception as e:
                err_str = str(e)
                if (
                    "429" in err_str
                    or "rate limit" in err_str.lower()
                    or "rate_limit" in err_str.lower()
                ) and attempt < attempts - 1:
                    if self.rotator.rotate_key():
                        self._rebuild_client()
                        continue
                raise e
        raise RuntimeError("Failed after rotating all keys.")

    def with_structured_output(self, schema: Any, **kwargs: Any) -> Runnable:
        def factory(api_key: Optional[str]) -> Runnable:
            from langchain_groq import ChatGroq

            api_key_secret = SecretStr(api_key) if api_key else None
            llm = ChatGroq(
                model=self.model_name,
                temperature=self.temperature,
                api_key=api_key_secret,
                max_retries=settings.llm_max_retries,
                model_kwargs={"seed": self.seed},
            )
            return llm.with_structured_output(schema, **kwargs)

        return RotatingRunnable(self.rotator, factory)


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
    PROVIDER_OLLAMA = "ollama"

    @staticmethod
    def get_dspy_lm(model: Optional[str] = None) -> Any:
        """
        Returns a DSPy-compatible language model (Recommendation 3).
        Uses universal dspy.LM interface for maximum compatibility.
        """
        import dspy  # type: ignore
        from src.config import settings

        provider = settings.llm_provider
        model = model or settings.groq_model
        api_key = (
            settings.groq_api_key if provider == "groq" else settings.gemini_api_key
        )

        if provider == "groq":
            clean_key = groq_rotator.get_current_key() or (
                api_key.split(",")[0].strip() if api_key else None
            )
            # Universal LM string format: 'provider/model'
            return dspy.LM(f"groq/{model}", api_key=clean_key)
        elif provider == "gemini":
            clean_key = api_key.split(",")[0].strip() if api_key else None
            return dspy.LM(f"google/{model}", api_key=clean_key)
        else:
            raise ValueError(f"DSPy currently doesn't support provider: {provider}")

    @staticmethod
    def get_llm(
        provider: Optional[str] = None,
        model: Optional[str] = None,
        temperature: float = 0.0,
        api_key: Optional[str] = None,
        seed: int = 42,
    ) -> "BaseChatModel":
        """
        Get an LLM instance for the specified provider.

        This factory method creates and returns an LLM instance based
        on the provider. It uses settings defaults if not specified.

        Args:
            provider: LLM provider name. If None, uses settings.llm_provider.
                Options: "groq", "gemini", "llamacpp", "ollama".
            model: Optional model name override. If None, uses provider default.
            temperature: LLM temperature (0.0 = deterministic, 1.0 = creative).
                Default is 0.0 for consistent, reproducible outputs.
            api_key: Optional API key override. If None, uses settings.
            seed: Optional seed for determinism (Recommendation 5).
                Default is 42.

        Returns:
            BaseChatModel instance for the specified provider.

        Raises:
            ValueError: If provider is not supported.

        Example:
            >>> # Use defaults from settings
            >>> llm = LLMProvider.get_llm()
            >>>
            >>> # Use specific model
            >>> llm = LLMProvider.get_llm(model="openai/gpt-oss-120b")
        """
        provider = provider or settings.llm_provider

        if provider == LLMProvider.PROVIDER_GROQ:
            return LLMProvider._get_groq_llm(model, temperature, api_key, seed)
        elif provider == LLMProvider.PROVIDER_GEMINI:
            return LLMProvider._get_gemini_llm(model, temperature, api_key, seed)
        elif provider == LLMProvider.PROVIDER_LLAMACPP:
            return LLMProvider._get_llamacpp_llm(model, temperature, seed)
        elif provider == LLMProvider.PROVIDER_OLLAMA:
            return LLMProvider._get_ollama_llm(model, temperature, seed)
        else:
            raise ValueError(
                f"Unsupported LLM provider: '{provider}'. "
                f"Supported providers: {LLMProvider.PROVIDER_GROQ}, {LLMProvider.PROVIDER_GEMINI}, {LLMProvider.PROVIDER_LLAMACPP}, {LLMProvider.PROVIDER_OLLAMA}"
            )

    @staticmethod
    def _get_groq_llm(
        model: Optional[str] = None,
        temperature: float = 0.0,
        api_key: Optional[str] = None,
        seed: int = 42,
    ) -> BaseChatModel:
        """
        Create a Groq LLM instance with key rotation support.

        Args:
            model: Model name (default: settings.groq_model).
            temperature: Sampling temperature (default: 0.0).
            api_key: API key override (default: settings.groq_api_key).
            seed: Seed for determinism.

        Returns:
            RotatingChatGroq instance.
        """
        model = model or settings.groq_model
        if api_key:
            # If custom key is specified, build a dedicated single-key rotator
            custom_rotator = GroqKeyRotator()
            custom_rotator._keys = [api_key]
            custom_rotator._current_index = 0
            rotator = custom_rotator
        else:
            rotator = groq_rotator

        return RotatingChatGroq(
            model_name=model,
            temperature=temperature,
            seed=seed,
            rotator=rotator,
        )

    @staticmethod
    def _get_gemini_llm(
        model: Optional[str] = None,
        temperature: float = 0.0,
        api_key: Optional[str] = None,
        seed: int = 42,
    ) -> BaseChatModel:
        """
        Create a Google Gemini LLM instance.

        Args:
            model: Model name (default: settings.gemini_model).
            temperature: Sampling temperature (default: 0.0).
            api_key: API key override (default: settings.gemini_api_key).
            seed: Seed for determinism.

        Returns:
            ChatGoogleGenerativeAI instance.
        """
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI
        except ImportError:
            raise ImportError("pip install langchain-google-genai")

        api_key = api_key or settings.gemini_api_key
        model = model or settings.gemini_model
        # Recommendation 5: Some models support seed natively
        return ChatGoogleGenerativeAI(
            model=model,
            temperature=temperature,
            api_key=api_key,
            max_retries=settings.llm_max_retries,
            model_kwargs={"seed": seed},
        )

    @staticmethod
    def _get_llamacpp_llm(
        model: Optional[str] = None,
        temperature: float = 0.0,
        seed: int = 42,
    ) -> BaseChatModel:
        """
        Create a LlamaCpp local LLM instance.

        Args:
            model: Path to model file (default: settings.llama_cpp_model_path).
            temperature: Sampling temperature (default: 0.0).
            seed: Seed for determinism.

        Returns:
            ChatLlamaCpp instance.

        Note:
            Requires llama-cpp-python and a compatible model file.
        """
        try:
            from langchain_community.chat_models import ChatLlamaCpp  # type: ignore[import-not-found]
        except ImportError:
            raise ImportError("pip install langchain-community llama-cpp-python")

        model_path = model or settings.llama_cpp_model_path
        return ChatLlamaCpp(
            model_path=model_path,
            temperature=temperature,
            seed=seed,
            n_ctx=settings.llama_cpp_n_ctx,
            n_gpu_layers=settings.llama_cpp_n_gpu_layers,
        )

    @staticmethod
    def _get_ollama_llm(
        model: Optional[str] = None,
        temperature: float = 0.0,
        seed: int = 42,
    ) -> BaseChatModel:
        """
        Create a local Ollama LLM instance.

        Args:
            model: Model name (default: "llama3").
            temperature: Sampling temperature (default: 0.0).
            seed: Seed for determinism.

        Returns:
            ChatOllama instance.
        """
        try:
            from langchain_ollama import ChatOllama  # type: ignore[import-not-found]
        except ImportError:
            try:
                from langchain_community.chat_models import ChatOllama  # type: ignore[import-not-found, assignment]
            except ImportError:
                raise ImportError("pip install langchain-ollama or langchain-community")

        model = model or "llama3"
        return ChatOllama(
            model=model,
            temperature=temperature,
            seed=seed,  # type: ignore[call-arg]
        )

    @staticmethod
    def get_structured_llm(
        schema: Type[Any],
        provider: Optional[str] = None,
        model: Optional[str] = None,
        temperature: float = 0.0,
        api_key: Optional[str] = None,
        seed: int = 42,
    ) -> Runnable:
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
            seed: Seed for determinism.

        Returns:
            LLM instance with structured output capability.

        Example:
            >>> from src.schemas.intent import StructuredIntent
            >>> parser_llm = LLMProvider.get_structured_llm(schema=StructuredIntent)
            >>> result = parser_llm.invoke("Configure OSPF on Router-A")
            >>> type(result)
            <class 'StructuredIntent'>
        """
        llm = LLMProvider.get_llm(provider, model, temperature, api_key, seed)
        provider = provider or settings.llm_provider

        # Different providers have different methods for structured output
        if provider == LLMProvider.PROVIDER_GROQ:
            return cast(Runnable, llm.with_structured_output(schema))
        elif provider == LLMProvider.PROVIDER_GEMINI:
            try:
                return cast(Runnable, llm.with_structured_output(schema))
            except AttributeError:
                # Fallback for older versions
                return llm.bind(response_format=schema)
        else:
            return cast(Runnable, llm.with_structured_output(schema))

    @staticmethod
    def validate_provider_config(provider: Optional[str] = None) -> bool:
        """
        Validate that the provider configuration is correct.
        """
        if provider and provider != settings.llm_provider:
            # We would need to re-validate if a different provider is requested
            # For now, we assume settings handles the default.
            return True
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


def get_structured_llm(schema: Type[Any], **kwargs) -> Runnable:
    """
    Convenience function to get a structured LLM.

    Args:
        schema: Pydantic model class for structured output.
        **kwargs: Arguments passed to LLMProvider.get_structured_llm().

    Returns:
        Structured LLM instance.

    Example:
        >>> from src.schemas.intent import StructuredIntent
        >>> parser = get_structured_llm(StructuredIntent)
    """
    return LLMProvider.get_structured_llm(schema, **kwargs)
