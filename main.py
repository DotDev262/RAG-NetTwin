import sys
import os
import json
from dotenv import load_dotenv

# Ensure src is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), 'src')))

from parser.intent_parser import IntentParser
from rag.config_generator import ConfigGenerator

def main():
    load_dotenv()
    
    print("="*60)
    print(" RAG-NetTwin: Hallucination-Mitigated Intent-Based Networking")
    print("="*60)
    
    if not os.getenv("GROQ_API_KEY") or os.getenv("GROQ_API_KEY") == "your_api_key_here":
        print("\n[!] Error: GROQ_API_KEY not set in .env file.")
        print("Please add your key to continue.\n")
        return

    # Initialize components
    try:
        parser = IntentParser()
        generator = ConfigGenerator()
    except Exception as e:
        print(f"\n[!] Initialization Error: {e}")
        return

    while True:
        print("\nEnter your network intent (or 'exit' to quit):")
        user_input = input("> ").strip()
        
        if user_input.lower() in ['exit', 'quit', 'q']:
            break
        
        if not user_input:
            continue
            
        try:
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
                
        except Exception as e:
            print(f"\n[!] Pipeline Error: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    main()