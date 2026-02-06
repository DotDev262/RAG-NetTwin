import sys
import os
import json

# Ensure src is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), 'src')))

from parser.intent_parser import IntentParser
from rag.config_generator import ConfigGenerator
from logger import setup_logger
from config import settings

# Initialize Logger
logger = setup_logger("CLI")

def main():
    logger.info("Starting RAG-NetTwin CLI")
    print("="*60)
    print(" RAG-NetTwin: Hallucination-Mitigated Intent-Based Networking")
    print("="*60)
    
    if not settings.groq_api_key or settings.groq_api_key == "your_api_key_here":
        logger.critical("GROQ_API_KEY not set in .env file")
        print("\n[!] Error: GROQ_API_KEY not set in .env file.")
        print("Please add your key to continue.\n")
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
        
        if user_input.lower() in ['exit', 'quit', 'q']:
            logger.info("User requested exit")
            break
        
        if not user_input:
            continue
            
        try:
            logger.info(f"Processing intent: {user_input}")
            print("\n[1/3] Parsing Intent...")
            structured_intent = parser.parse(user_input)
            print(f"      ✓ Intent parsed: {structured_intent.protocol} {structured_intent.action}")
            
            print("\n[2/3] Retrieving Documentation & Generating Config...")
            configs = generator.generate(structured_intent)
            
            print("\n[3/3] Results:")
            print("-" * 40)
            for device_name, data in configs.items():
                print(f"Device: {device_name}")
                print(f"Retrieved {len(data['retrieved_sources'])} references.")
                print("\nGenerated Configuration:")
                print("```")
                print(data['config'])
                print("```")
                print("-" * 40)
            
            logger.info("Intent processing complete")
                
        except Exception as e:
            logger.error(f"Pipeline Error: {e}", exc_info=True)
            print(f"\n[!] Pipeline Error: {e}")

if __name__ == "__main__":
    main()