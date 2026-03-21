import sys
import os
import json

# Ensure src is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "src")))

from parser.intent_parser import IntentParser
from rag.config_generator import ConfigGenerator
from utils import setup_logger
from config import settings, validate_llm_config
from llm import LLMProvider

# Initialize Logger
logger = setup_logger("CLI")


def main():
    logger.info("Starting RAG-NetTwin CLI")
    print("=" * 60)
    print(" RAG-NetTwin: Hallucination-Mitigated Intent-Based Networking")
    print("=" * 60)

    # Validate LLM configuration
    try:
        validate_llm_config()
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

    # Initialize components
    try:
        parser = IntentParser()
        generator = ConfigGenerator()
        logger.info("Components initialized successfully")
    except Exception as e:
        logger.error(f"Initialization Error: {e}", exc_info=True)
        print(f"\n[!] Initialization Error: {e}")
        return

    while True:
        print("\nEnter your network intent (or 'exit' to quit):")
        user_input = input("> ").strip()

        if user_input.lower() in ["exit", "quit", "q"]:
            logger.info("User requested exit")
            break

        if not user_input:
            continue

        try:
            logger.info(f"Processing intent: {user_input}")
            print("\n[1/3] Parsing Intent...")
            structured_intent = parser.parse(user_input)
            print(
                f"      ✓ Intent parsed: {structured_intent.protocol} {structured_intent.action}"
            )

            print("\n[2/3] Retrieving Documentation & Generating Config...")
            configs = generator.generate(structured_intent)

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

                # Optional: Tier 1 Validation (Batfish)
                try:
                    from validation.batfish_validator import BatfishValidator

                    print("\n[4/4] Running Tier 1 Validation (Batfish)...")
                    validator = BatfishValidator()
                    # Batfish expects a mapping of hostname -> config
                    validation_result = validator.validate({device_name: data["config"]}, structured_intent)

                    if validation_result.get("status") in ["PASS", "WARNING"]:
                        print(f"✅ Tier 1 Validation {validation_result.get('status')}")
                    else:
                        print(f"⚠️  Tier 1 Validation {validation_result.get('status')}:")
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
