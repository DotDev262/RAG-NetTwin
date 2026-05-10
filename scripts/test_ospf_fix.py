from src.parser.intent_parser import IntentParser
from src.rag.config_generator import ConfigGenerator
from src.validation.batfish_validator import BatfishValidator
from src.evaluation.hallucination_detector import HallucinationDetector


def test_ospf_hello():
    parser = IntentParser()
    generator = ConfigGenerator()
    validator = BatfishValidator()
    detector = HallucinationDetector()

    intent_text = (
        "Align OSPF hello-interval to 5 seconds on both Cisco and Juniper routers"
    )
    print(f"\nEvaluating: {intent_text}")

    intent = parser.parse(intent_text)
    output = generator.generate(intent, retrieval_mode="tiered")

    # Extract master plan if present in trace
    master_plan = output.get("_trace", {}).get("master_plan")

    for dev_name, dev_data in output.items():
        if dev_name.startswith("_"):
            continue
        print(f"\n--- {dev_name} Config ---")
        print(dev_data["config"])

        hal_report = detector.detect(
            dev_data["config"],
            dev_data.get("retrieved_sources", []),
            dev_data.get("valid_source_ids", []),
            retrieved_texts=[dev_data.get("grounding_context", "")],
            intent_context=intent_text,
            intent_params=intent.parameters,
            master_plan=master_plan,
        )
        print(f"Hallucinated: {hal_report.is_hallucinated}")
        if hal_report.is_hallucinated:
            print(f"Reason: {hal_report.reason}")

    # Validation
    configs = {k: v["config"] for k, v in output.items() if not k.startswith("_")}
    val_report = validator.validate(configs, intent)
    print(f"\nValidation Status: {val_report['status']}")


if __name__ == "__main__":
    test_ospf_hello()
