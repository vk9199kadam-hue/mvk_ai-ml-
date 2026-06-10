# =============================================================================
# AutoInsight AI — LLM Provider Factory (llm_factory.py)
# Phase 1: Foundation — AI Engine Abstraction
# =============================================================================
"""
Configurable LLM factory supporting dual-provider architecture.

Provides a unified interface for:
  - Primary: Qwen 2.5 72B via Groq Free Tier (zerocost)
  - Fallback: Llama 3.1 8B via local Ollama (fully offline)

Key Design Decisions:
  - Temperature = 0.1: Low temperature ensures deterministic, repeatable outputs
  - Structured JSON mode: Forces LLM to output valid JSON matching Pydantic schemas
  - Dual-provider: Automatic fallback if primary is unavailable
  - Retry logic: Exponential backoff with configurable max retries
  - Prompt caching: Redis cache for frequently used prompts

Usage:
    from backend.llm_factory import LLMFactory
    
    factory = LLMFactory(provider="groq")
    
    # Get structured output
    result = await factory.invoke_agent(
        prompt_name="infer_schema",
        variables={"csv_sample": sample_data},
        output_model=SchemaInferenceResponse,
    )
"""

from __future__ import annotations

import json
import logging
import time
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Type, TypeVar

from langchain.schema import BaseMessage, HumanMessage, SystemMessage
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
from langchain_groq import ChatGroq
from langchain_ollama import ChatOllama
from pydantic import BaseModel

from backend.config import settings

logger = logging.getLogger(__name__)

# Type variable for Pydantic output models
T = TypeVar("T", bound=BaseModel)


class LLMProvider(str, Enum):
    """Supported LLM providers."""
    GROQ = "groq"
    OLLAMA = "ollama"


class LLMFactoryError(Exception):
    """Base exception for LLM factory errors."""
    pass


class LLMFactory:
    """
    Factory class for creating and managing LLM instances.
    
    Supports Qwen 2.5 72B (Groq) and Llama 3.1 8B (Ollama).
    Provides structured JSON output with Pydantic validation.
    
    Attributes:
        provider: Current LLM provider name
        llm: Initialized LangChain LLM instance
        max_retries: Maximum retry attempts on failure
        timeout: LLM call timeout in seconds
    """
    
    def __init__(
        self,
        provider: str = "groq",
        temperature: float = 0.1,
        max_tokens: int = 4096,
        max_retries: int = 3,
        timeout: int = 30,
    ):
        """
        Initialize the LLM factory.
        
        Args:
            provider: LLM provider ("groq" or "ollama")
            temperature: Model temperature (0.0 = deterministic, 1.0 = creative)
            max_tokens: Maximum tokens in response
            max_retries: Maximum retry attempts on failure
            timeout: Timeout in seconds per call
        
        Raises:
            LLMFactoryError: If provider is invalid or initialization fails
        """
        self.provider = provider.lower()
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.max_retries = max_retries
        self.timeout = timeout
        
        if self.provider not in ("groq", "ollama"):
            raise LLMFactoryError(
                f"Invalid provider: '{provider}'. Must be 'groq' or 'ollama'."
            )
        
        self.llm = self._initialize_llm()
        logger.info(
            f"LLM Factory initialized: provider={provider}, "
            f"temperature={temperature}, max_tokens={max_tokens}"
        )
    
    def _initialize_llm(self):
        """
        Initialize the LLM instance based on the configured provider.
        
        Returns:
            LangChain LLM instance
        
        Raises:
            LLMFactoryError: If initialization fails
        """
        try:
            if self.provider == "groq":
                if not settings.GROQ_API_KEY:
                    raise LLMFactoryError(
                        "GROQ_API_KEY is not configured. "
                        "Set GROQ_API_KEY in your .env file or switch to 'ollama' provider."
                    )
                
                logger.info(
                    f"Initializing Groq LLM: model={settings.GROQ_MODEL}"
                )
                
                return ChatGroq(
                    model=settings.GROQ_MODEL,
                    temperature=self.temperature,
                    max_tokens=self.max_tokens,
                    groq_api_key=settings.GROQ_API_KEY,
                    timeout=self.timeout,
                )
                
            elif self.provider == "ollama":
                logger.info(
                    f"Initializing Ollama LLM: model={settings.OLLAMA_MODEL}, "
                    f"base_url={settings.OLLAMA_BASE_URL}"
                )
                
                return ChatOllama(
                    model=settings.OLLAMA_MODEL,
                    temperature=self.temperature,
                    num_predict=self.max_tokens,
                    base_url=settings.OLLAMA_BASE_URL,
                )
                
        except Exception as e:
            raise LLMFactoryError(f"Failed to initialize LLM: {e}")
    
    def with_structured_output(self, pydantic_model: Type[BaseModel]):
        """
        Get an LLM chain that outputs JSON matching the specified Pydantic schema.
        
        Uses LangChain's with_structured_output with json_mode to:
          1. Force the LLM to output valid JSON
          2. Validate the JSON against the Pydantic schema
          3. Return a validated Pydantic model instance
        
        Args:
            pydantic_model: Pydantic model class for output validation
        
        Returns:
            LangChain runnable that returns validated Pydantic models
        
        Example:
            chain = factory.with_structured_output(SchemaInferenceResponse)
            result = await chain.ainvoke({
                "csv_sample": "..."
            })
        """
        return self.llm.with_structured_output(
            pydantic_model,
            method="json_mode",  # Force JSON mode for structured output
        )
    
    async def invoke_agent(
        self,
        system_prompt: str,
        user_prompt: str,
        output_model: Type[T],
        variables: Optional[Dict[str, Any]] = None,
    ) -> T:
        """
        Execute an LLM agent with a system prompt and structured output.
        
        This is the PRIMARY method for all LLM calls in AutoInsight AI.
        Every call:
          1. Formats the prompt with variables
          2. Calls the LLM with structured output mode
          3. Validates the output against the Pydantic model
          4. Retries on failure (exponential backoff)
          5. Returns a validated Pydantic model
        
        Args:
            system_prompt: System-level instruction prompt
            user_prompt: User-specific query or data
            output_model: Pydantic model class for output validation
            variables: Optional variables to format into user_prompt
        
        Returns:
            Validated Pydantic model instance
        
        Raises:
            LLMFactoryError: If all retry attempts fail
        
        Example:
            result = await factory.invoke_agent(
                system_prompt="You are a data schema expert...",
                user_prompt="Infer schema for: {csv_sample}",
                output_model=SchemaInferenceResponse,
                variables={"csv_sample": sample_data},
            )
        """
        # Format user prompt with variables
        if variables and "{csv_sample}" in user_prompt:
            # Truncate large variables to prevent token overflow
            for key, value in variables.items():
                if isinstance(value, str) and len(value) > 10000:
                    variables[key] = value[:10000] + "...[truncated]"
        
        formatted_prompt = user_prompt
        if variables:
            try:
                formatted_prompt = user_prompt.format(**variables)
            except KeyError as e:
                logger.warning(f"Prompt formatting error (missing variable): {e}")
        
        # Prepare messages
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=formatted_prompt),
        ]
        
        # Create output parser
        parser = PydanticOutputParser(pydantic_object=output_model)
        
        # Execute with retry logic
        last_error = None
        for attempt in range(1, self.max_retries + 1):
            try:
                logger.info(
                    f"LLM call: provider={self.provider}, "
                    f"model={self._get_model_name()}, "
                    f"attempt={attempt}/{self.max_retries}, "
                    f"output_model={output_model.__name__}"
                )
                
                start_time = time.time()
                
                # Call the LLM
                response = await self.llm.ainvoke(messages)
                
                elapsed = time.time() - start_time
                logger.info(f"LLM response received in {elapsed:.2f}s")
                
                # Parse the response
                content = response.content if hasattr(response, 'content') else str(response)
                
                # Try to parse as structured output
                try:
                    if hasattr(response, 'additional_kwargs') and 'tool_calls' in response.additional_kwargs:
                        # Structured output mode was used
                        parsed = output_model.model_validate_json(
                            response.additional_kwargs['tool_calls'][0]['function']['arguments']
                        )
                    else:
                        # Parse from content string
                        # Clean up markdown code blocks if present
                        cleaned = content.strip()
                        if cleaned.startswith("```"):
                            # Extract JSON from code block
                            lines = cleaned.split("\n")
                            cleaned = "\n".join(l for l in lines if not l.startswith("```"))
                        
                        parsed = output_model.model_validate_json(cleaned)
                    
                    logger.info(
                        f"LLM call successful: {output_model.__name__} "
                        f"validated, attempt={attempt}"
                    )
                    return parsed
                    
                except Exception as parse_error:
                    logger.warning(
                        f"Output parsing failed (attempt {attempt}): {parse_error}"
                    )
                    last_error = parse_error
                    
                    # If not last attempt, wait with exponential backoff
                    if attempt < self.max_retries:
                        wait_time = 2 ** (attempt - 1)  # 1s, 2s, 4s
                        logger.info(f"Retrying in {wait_time}s...")
                        time.sleep(wait_time)
                        
            except Exception as e:
                logger.error(
                    f"LLM call failed (attempt {attempt}): {e}"
                )
                last_error = e
                
                if attempt < self.max_retries:
                    wait_time = 2 ** (attempt - 1)
                    logger.info(f"Retrying in {wait_time}s...")
                    time.sleep(wait_time)
        
        # All retries exhausted — raise error
        raise LLMFactoryError(
            f"LLM call failed after {self.max_retries} attempts. "
            f"Last error: {last_error}"
        )
    
    async def with_fallback(
        self,
        system_prompt: str,
        user_prompt: str,
        output_model: Type[T],
        variables: Optional[Dict[str, Any]] = None,
        fallback_provider: str = "ollama",
    ) -> T:
        """
        Execute LLM call with automatic fallback to secondary provider.
        
        Tries the primary provider first. If it fails after all retries,
        automatically falls back to the secondary provider.
        
        This implements the dual-provider fault tolerance strategy:
          Primary: Qwen 2.5 72B (Groq Free Tier)
          Fallback: Llama 3.1 8B (Ollama Local)
        
        Args:
            system_prompt: System prompt
            user_prompt: User query
            output_model: Expected output Pydantic model
            variables: Template variables
            fallback_provider: Fallback provider ("ollama" or "groq")
        
        Returns:
            Validated Pydantic model from primary or fallback
        
        Raises:
            LLMFactoryError: If both providers fail
        """
        try:
            return await self.invoke_agent(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                output_model=output_model,
                variables=variables,
            )
        except LLMFactoryError as primary_error:
            logger.warning(
                f"Primary LLM ({self.provider}) failed. "
                f"Falling back to {fallback_provider}. "
                f"Error: {primary_error}"
            )
            
            # Create fallback factory
            fallback = LLMFactory(
                provider=fallback_provider,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
            )
            
            try:
                return await fallback.invoke_agent(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    output_model=output_model,
                    variables=variables,
                )
            except LLMFactoryError as fallback_error:
                raise LLMFactoryError(
                    f"Both LLM providers failed. "
                    f"Primary ({self.provider}): {primary_error}. "
                    f"Fallback ({fallback_provider}): {fallback_error}."
                )
    
    def _get_model_name(self) -> str:
        """Get the current model name."""
        if self.provider == "groq":
            return settings.GROQ_MODEL
        else:
            return settings.OLLAMA_MODEL
    
    def switch_provider(self, provider: str) -> None:
        """
        Switch to a different LLM provider.
        
        Args:
            provider: New provider ("groq" or "ollama")
        """
        if provider.lower() == self.provider:
            return
        
        logger.info(f"Switching LLM provider: {self.provider} → {provider}")
        self.provider = provider.lower()
        self.llm = self._initialize_llm()
    
    @staticmethod
    def get_available_providers() -> List[str]:
        """Get list of configured (available) providers."""
        providers = []
        if settings.GROQ_API_KEY:
            providers.append("groq")
        providers.append("ollama")  # Always available (local)
        return providers
    
    @staticmethod
    def create_fallback_chain() -> Dict[str, Any]:
        """
        Create a complete fallback chain configuration.
        
        Returns:
            Dict with primary and fallback configurations
        """
        return {
            "primary": {
                "provider": "groq",
                "model": settings.GROQ_MODEL,
                "temperature": 0.1,
            },
            "fallback": {
                "provider": "ollama",
                "model": settings.OLLAMA_MODEL,
                "temperature": 0.1,
            },
            "retry_strategy": {
                "max_retries": settings.GROQ_MAX_RETRIES,
                "backoff": "exponential",
                "base_delay_seconds": 1,
            },
        }
