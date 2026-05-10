
import unittest
from src.evaluation.hallucination_detector import HallucinationDetector

class TestHallucinationDetector(unittest.TestCase):
    def setUp(self):
        self.detector = HallucinationDetector()

    def test_common_masks_not_hallucinated(self):
        # Test that common subnet masks and wildcards are not flagged as unauthorized parameters
        config = "interface GigabitEthernet0/1\n ip address 10.1.1.1 255.255.255.0\n ip access-list standard 10\n permit 10.1.1.0 0.0.0.255"
        intent_params = {"ip": "10.1.1.1", "network": "10.1.1.0"}
        
        report = self.detector.detect(
            config=config,
            citations=[],
            valid_source_ids=[],
            intent_params=intent_params
        )
        
        # Currently, this might fail because 255.255.255.0 and 0.0.0.255 are not in authorized_values
        self.assertNotIn("255.255.255.0", report.unauthorized_parameters)
        self.assertNotIn("0.0.0.255", report.unauthorized_parameters)

    def test_common_bgp_commands_grounded(self):
        # Test that common BGP commands like 'activate' are not flagged as ungrounded
        config = "router bgp 65001\n address-family ipv4\n neighbor 192.168.1.1 activate"
        
        # Mock documentation that DOES NOT contain 'activate' explicitly but 'neighbor' and 'bgp'
        retrieved_texts = ["router bgp AS-NUMBER", "neighbor IP-ADDRESS remote-as AS-NUMBER"]
        
        report = self.detector.detect(
            config=config,
            citations=[],
            valid_source_ids=[],
            retrieved_texts=retrieved_texts,
            intent_params={"asn": "65001", "neighbor": "192.168.1.1"}
        )
        
        # 'activate' and 'address-family' should be considered common enough to not need explicit grounding
        self.assertNotIn("neighbor 192.168.1.1 activate", report.ungrounded_commands)
        self.assertNotIn("address-family ipv4", report.ungrounded_commands)

if __name__ == "__main__":
    unittest.main()
