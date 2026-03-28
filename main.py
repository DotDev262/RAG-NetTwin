"""
Main CLI Entry Point for RAG-NetTwin.

This module provides an interactive command-line interface for the
RAG-NetTwin system. Users can enter natural language intents and
receive generated network configurations.

Pipeline Flow:
1. Parse: Convert natural language to StructuredIntent
2. Generate: Use RAG to retrieve docs and generate config
3. Validate: Optional Tier 1 validation with Batfish

Key Features:
- Interactive CLI with progress indicators
- LLM configuration validation
- Optional Batfish validation
- Structured logging throughout

Typical Usage:
    python main.py

    # Then enter intents like:
    # "Configure OSPF area 0 on Router-A for interface Gig0/1"
"""

import sys
import os
import json

# Ensure src is in path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "src")))

from parser.intent_parser import IntentParser
from rag.config_generator import ConfigGenerator
from utils import setup_logger
from config import settings
from llm import LLMProvider

# Initialize Logger for this module
logger = setup_logger("CLI")


def main():
    """
    Main CLI entry point.

    This function runs an interactive loop that:
    1. Validates LLM configuration at startup
    2. Initializes parser and generator components
    3. Accepts user input in a loop
    4. Processes each intent through the full pipeline
    5. Optionally runs Tier 1 validation

    The function exits cleanly on 'exit', 'quit', or 'q'.
    """
    logger.info("Starting RAG-NetTwin CLI")
    print("=" * 60)
    print(" RAG-NetTwin: Hallucination-Mitigated Intent-Based Networking")
    print("=" * 60)

    # Validate LLM configuration before starting
    # This ensures API keys are present for the selected provider
    try:
        settings.validate_config()
        logger.info(f"Using LLM provider: {settings.llm_provider}")
        print(f"\n✓ LLM Provider: {settings.llm_provider}")
    except ValueError as e:
        logger.critical(f"LLM Configuration Error: {e}")
        print(f"\n[!] Configuration Error: {e}")
        print("\nPlease set the appropriate API key in your .env file:")
        print(f"  - For Groq: GROQ_API_KEY")
        print(f"  - For Gemini: GEMINI_API_KEY")
        print(f"\nCurrent provider setting: {settings.llm_provider}")
        return

    # Initialize core components
    # IntentParser: Converts NL to StructuredIntent
    # ConfigGenerator: Generates configs from intents
    try:
        parser = IntentParser()
        generator = ConfigGenerator()
        logger.info("Components initialized successfully")
    except Exception as e:
        logger.error(f"Initialization Error: {e}", exc_info=True)
        print(f"\n[!] Initialization Error: {e}")
        return

    # Main interaction loop
    while True:
        print("\nEnter your network intent (or 'exit' to quit):")
        user_input = input("> ").strip()

        # Check for exit commands
        if user_input.lower() in ["exit", "quit", "q"]:
            logger.info("User requested exit")
            break

        # Skip empty input
        if not user_input:
            continue

        try:
            logger.info(f"Processing intent: {user_input}")

            # Step 1: Parse the natural language intent
            print("\n[1/3] Parsing Intent...")
            structured_intent = parser.parse(user_input)
            print(
                f"      ✓ Intent parsed: {structured_intent.protocol} {structured_intent.action}"
            )

            # Step 2: Retrieve docs and generate configuration
            print("\n[2/3] Retrieving Documentation & Generating Config...")
            configs = generator.generate(structured_intent)

            # Step 3: Display results
            print("\n[3/3] Results:")
            print("-" * 40)
            for device_name, data in configs.items():
                print(f"Device: {device_name}")
                print(f"Retrieved {len(data['retrieved_sources'])} references.")
                print("\nGenerated Configuration:")
                print("```")
                print(data["config"])
                print("```")
                print("-" * 40)

                # Optional Step 4: Run Tier 1 validation (Batfish)
                # This catches syntax errors before deployment
                try:
                    from validation.batfish_validator import BatfishValidator

                    print("\n[4/4] Running Tier 1 Validation (Batfish)...")
                    validator = BatfishValidator()
                    # Batfish expects a mapping of hostname -> config
                    validation_result = validator.validate(
                        {device_name: data["config"]}, structured_intent
                    )

                    if validation_result.get("status") in ["PASS", "WARNING"]:
                        print(f"✅ Tier 1 Validation {validation_result.get('status')}")
                    else:
                        print(
                            f"⚠️  Tier 1 Validation {validation_result.get('status')}:"
                        )
                        for issue in validation_result.get("issues", [])[:3]:
                            print(f"   - [{issue['type']}] {issue['details']}")
                except Exception as e:
                    print(f"\n⚠️  Tier 1 Validation not available: {e}")
                    print(
                        "   Start validators: sudo ./scripts/install_validators_ubuntu.sh --verify"
                    )

            logger.info("Intent processing complete")

        except Exception as e:
            logger.error(f"Pipeline Error: {e}", exc_info=True)
            print(f"\n[!] Pipeline Error: {e}")


if __name__ == "__main__":
    main()
