from src.rag.config_generator import ConfigGenerator
from src.schemas.intent import StructuredIntent, DeviceIntent


def test_generation():
    generator = ConfigGenerator()
    intent = StructuredIntent(
        intent_id="test_1",
        protocol="OSPF",
        action="configure",
        devices=[DeviceIntent(name="Cisco", vendor="cisco", os_type="ios-xe")],
        parameters={"area": "0", "interface": "Gig1"},
        original_text="Configure OSPF area 0 on Gig1",
    )

    try:
        output = generator.generate(intent, retrieval_mode="none")
        print("Generation successful!")
        for dev, data in output.items():
            if dev.startswith("_"):
                continue
            print(f"Device: {dev}")
            print(f"Config:\n{data['config']}")
    except Exception as e:
        print(f"Generation failed: {e}")


if __name__ == "__main__":
    test_generation()
