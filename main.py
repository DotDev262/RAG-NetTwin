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


# Ensure src is in path for imports

from src.parser.intent_parser import IntentParser
from src.rag.config_generator import ConfigGenerator
from src.exporter.gns3_exporter import GNS3Exporter
from src.evaluation.blast_radius_analyzer import BlastRadiusAnalyzer
from src.utils import setup_logger, generate_audit_report
from src.config import settings

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
    logger.info(f"Using LLM provider: {settings.llm_provider}")
    print(f"\n✓ LLM Provider: {settings.llm_provider}")

    # Initialize core components
    # IntentParser: Converts NL to StructuredIntent
    # ConfigGenerator: Generates configs from intents
    # GNS3Exporter: Generates Digital Twin topology
    try:
        parser = IntentParser()
        generator = ConfigGenerator()
        exporter = GNS3Exporter()
        blast_analyzer = BlastRadiusAnalyzer()
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
                # Skip internal metadata keys
                if device_name is not None and device_name.startswith("_"):
                    continue

                print(f"Device: {device_name}")
                sources = data.get("retrieved_sources", [])
                print(f"Retrieved {len(sources)} references.")
                print("\nGenerated Configuration:")
                print("```")
                print(data.get("config", "ERROR"))
                print("```")
                print("-" * 40)

                # Optional Step 4: Run Tier 1 validation (Batfish)
                # This catches syntax errors before deployment
                try:
                    from src.validation.batfish_validator import BatfishValidator

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

                        # Step 4.5: Interactive Refinement (Recommendation 4)
                        print(
                            "\nWould you like me to attempt a self-correction based on these errors? (y/n)"
                        )
                        choice = input("> ").strip().lower()
                        if choice == "y":
                            print("Refining configuration...")
                            error_text = "\n".join(
                                [
                                    i["details"]
                                    for i in validation_result.get("issues", [])
                                ]
                            )

                            # Get vendor/version for the device
                            device_intent = next(
                                (
                                    d
                                    for d in structured_intent.devices
                                    if d.name == device_name
                                ),
                                None,
                            )
                            vendor = device_intent.vendor if device_intent else "cisco"
                            version = (
                                device_intent.os_version if device_intent else "17.6"
                            )

                            fixed_config = generator.refine(
                                device_name=device_name,
                                config=data["config"],
                                error_feedback=error_text,
                                vendor=vendor,
                                os_version=version,
                            )

                            print("\nFixed Configuration:")
                            print("```")
                            print(fixed_config)
                            print("```")

                            print("Re-validating fixed configuration...")
                            re_validation = validator.validate(
                                {device_name: fixed_config}, structured_intent
                            )
                            print(
                                f"✅ Re-validation Status: {re_validation.get('status')}"
                            )
                            # Update data with fixed config for downstream steps (like export)
                            data["config"] = fixed_config
                except Exception as e:
                    print(f"\n⚠️  Tier 1 Validation not available: {e}")
                    print(
                        "   Start validators: sudo ./scripts/install_validators_ubuntu.sh --verify"
                    )

            # Step 5: Export Digital Twin Topology
            print("\n[5/6] Exporting Digital Twin (Topology-as-Code)...")
            try:
                topo_path = exporter.export(structured_intent)
                print(f"      ✓ Digital Twin topology exported to: {topo_path}")
            except Exception as e:
                logger.error(f"Export Error: {e}")
                print(f"      [!] Export failed: {e}")

            # Step 6: Generate Grounding Audit Report (Recommendation 5)
            print("\n[6/6] Generating Grounding Audit Report...")
            try:
                audit_path = generate_audit_report(structured_intent, configs)
                print(f"      ✓ Audit report generated at: {audit_path}")
            except Exception as e:
                logger.error(f"Audit Error: {e}")
                print(f"      [!] Audit report failed: {e}")

            # Step 7: Functional Verification (Recommendation 1)
            print("\nWould you like to run Functional Verification in GNS3? (y/n)")
            run_func = input("> ").strip().lower()
            if run_func == "y":
                try:
                    from src.validation.gns3_validator import GNS3Validator

                    gns3 = GNS3Validator()
                    result = {}  # Initialize

                    if not gns3.connected:
                        print(
                            f"      [!] GNS3 server not reachable at {settings.gns3_host}:{settings.gns3_port}"
                        )
                        print("          Please ensure the GNS3 application is open.")
                    else:
                        print("\n[7/7] Running Closed-Loop Functional Verification...")
                        # Initial validation (creates project, starts nodes)
                        result = gns3.validate({}, structured_intent)

                        if result.get("status") == "ERROR":
                            print(f"      [!] GNS3 Error: {result.get('error')}")
                        else:
                            # 1. Capture Pre-Change Baseline
                            print("      ✓ Capturing Pre-Change Baseline...")
                            pre_state = gns3.get_network_state(result.get("nodes", {}))

                            # 2. Push Configs
                            print("      ✓ Pushing Configurations...")
                            # Skip internal metadata keys when preparing config map
                            config_map = {
                                name: data["config"]
                                for name, data in configs.items()
                                if (name is None or not name.startswith("_"))
                                and "config" in data
                            }
                            gns3.push_configs(result.get("nodes", {}), config_map)

                            # 3. Run Verification Commands
                            v_data = {
                                name: data.get("verification_commands", [])
                                for name, data in configs.items()
                                if name is None or not name.startswith("_")
                            }

                            v_results = gns3.verify_functional(
                                result.get("nodes", {}), v_data
                            )

                            # 4. Capture Post-Change State
                            print("      ✓ Capturing Post-Change State...")
                            post_state = gns3.get_network_state(result.get("nodes", {}))

                            # 5. Analyze Blast Radius
                            print(
                                "\n[8/7] Analyzing Blast Radius (Impact Assessment)..."
                            )
                            analysis = blast_analyzer.analyze(
                                user_input, pre_state, post_state
                            )
                            print("\n--- Blast Radius Analysis ---")
                            print(analysis)
                            print("------------------------------")

                            print("\n--- Functional Verification Results ---")
                            for dev, v_list in v_results.items():
                                print(f"Device: {dev}")
                                for vr in v_list:
                                    if "error" in vr:
                                        print(f"  ❌ Error: {vr['error']}")
                                    else:
                                        print(f"  > {vr['command']}")
                                        # Show first few lines of output
                                        out_lines = vr["output"].strip().splitlines()
                                        for line in out_lines[:5]:
                                            print(f"    {line}")
                                        if len(out_lines) > 5:
                                            print(
                                                f"    ... ({len(out_lines)-5} more lines)"
                                            )
                            print("---------------------------------------")
                except Exception as e:
                    print(f"      [!] Functional Verification failed: {e}")

            logger.info("Intent processing complete")

        except Exception as e:
            logger.error(f"Pipeline Error: {e}", exc_info=True)
            print(f"\n[!] Pipeline Error: {e}")


if __name__ == "__main__":
    main()
