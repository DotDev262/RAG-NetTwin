import pytest
from src.rag.parameter_normalizer import ParameterNormalizer


def test_post_process_config_cisco_route():
    config = "ip route 10.0.0.0/24 192.168.1.1"
    processed = ParameterNormalizer.post_process_config(config, "cisco")
    assert "10.0.0.0 255.255.255.0" in processed


def test_post_process_config_cisco_interface():
    # Test GigabitEthernet mapping
    config = "interface Gig1/0/1\n ip address 10.1.1.1 255.255.255.0"
    processed = ParameterNormalizer.post_process_config(config, "cisco")
    assert "interface Ethernet1/0/1" in processed

    # Test Gi mapping
    config = "interface Gi0/1"
    processed = ParameterNormalizer.post_process_config(config, "cisco")
    assert "interface Ethernet0/1" in processed


def test_post_process_config_qos_cleanup():
    # Test stripping 'type qos'
    config = "policy-map type qos QoS-OSPF\n class type traffic CS6\n  set dscp cs6"
    processed = ParameterNormalizer.post_process_config(config, "cisco")
    assert "policy-map QoS-OSPF" in processed
    assert "class CS6" in processed
    # Also check DSCP normalization
    assert "set dscp 48" in processed


def test_post_process_config_qos_repair():
    # Test flat QoS repair
    # Case: policy-map followed directly by set dscp
    # Should inject 'class <name>'
    config = """
ip access-list extended CS6_ACL
 permit ospf any any
class-map match-all CS6_CLASS
policy-map QoS_POLICY
 set dscp 48
"""
    processed = ParameterNormalizer.post_process_config(config, "cisco")
    assert "class CS6_CLASS" in processed
    assert "  set dscp 48" in processed

    # Check that it injected 'match' if missing
    config = """
ip access-list extended CS6_ACL
 permit ospf any any
class-map match-all CS6_CLASS
policy-map QoS_POLICY
 class CS6_CLASS
  set dscp 48
"""
    processed = ParameterNormalizer.post_process_config(config, "cisco")
    assert "match access-group name CS6_ACL" in processed


def test_post_process_config_no_cleanup():
    # Test that 'no policy-map type qos' -> 'no policy-map'
    config = "no policy-map type qos QoS"
    processed = ParameterNormalizer.post_process_config(config, "cisco")
    assert processed == "no policy-map QoS"


if __name__ == "__main__":
    pytest.main([__file__])
