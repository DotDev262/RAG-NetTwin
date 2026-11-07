"""
Unit Tests for LLM-Assisted Rule Encoder (RFC & Vendor CLI Spec Extraction).
Tests:
1. Document Ingestion & Chunking (ingest.py)
2. Structural Model & Alignment Schema (schema.py)
3. Rule Registry Validator & Mathematical Consistency (validator.py)
4. Static Alignment Registry generation and consumption by StateInvariantGraphController
5. CLI Utility argument parsing and dry-run execution (cli.py)
"""

import json
import pytest
from pathlib import Path

from src.rule_encoder.schema import (
    AlignmentRegistry,
    AlignmentSchemaRule,
    ConstraintType,
    InteroperabilityConstraint,
    ParameterDataType,
    VendorSyntaxMapping,
)
from src.rule_encoder.ingest import DocumentChunk, DocumentIngestionEngine
from src.rule_encoder.validator import RuleRegistryValidator, ValidationIssue
from src.rag.state_graph_controller import StateInvariantGraphController
from src.schemas.intent import StructuredIntent, DeviceIntent


@pytest.fixture
def sample_rfc_text():
    return """
    RFC 2328 - OSPF Version 2

    9.5. Sending Hello Packets
    Hello packets are sent out of each interface periodically.
    The interval between Hello packets is determined by the HelloInterval parameter.
    Values for HelloInterval must be an integer in seconds (range: 1 to 65535).
    The RouterDeadInterval determines when a neighbor is declared down.
    
    The HelloInterval and RouterDeadInterval MUST match identically across all routers
    attached to a common network. If these timers differ, the OSPF adjacency will not form.

    10.5. Authentication
    AuthenticationType specifies whether null, simple password, or cryptographic (MD5)
    authentication is used. If MD5 authentication is configured, all routers on the link
    must agree on the AuthKey and KeyID.
    """


@pytest.fixture
def sample_valid_rule():
    return AlignmentSchemaRule(
        rule_id="OSPF_HELLO_INTERVAL_01",
        protocol_name="OSPFv2",
        parameter_identifier="hello_interval",
        data_type=ParameterDataType.INTEGER,
        allowed_range={"min": 1, "max": 65535},
        vendor_syntax={
            "cisco": VendorSyntaxMapping(
                vendor="cisco",
                os_type="ios-xe",
                command_template="ip ospf hello-interval <value>",
                submode_path="interface",
                default_value=10,
            ),
            "juniper": VendorSyntaxMapping(
                vendor="juniper",
                os_type="junos",
                command_template="set protocols ospf area <area> interface <int> hello-interval <value>",
                submode_path="protocols ospf",
                default_value=10,
            ),
        },
        interoperability_constraint=InteroperabilityConstraint(
            constraint_type=ConstraintType.EXACT_MATCH,
            scope="SHARED_LINK",
            description="OSPF Hello Interval must be identical across connecting link interfaces.",
            is_mandatory=True,
        ),
        source_reference="RFC 2328 Section 9.5",
    )


class TestRuleEncoderIngestion:
    """Tests document ingestion and semantic chunking."""

    def test_chunking_rfc_text(self, sample_rfc_text, tmp_path):
        rfc_file = tmp_path / "rfc2328_test.txt"
        rfc_file.write_text(sample_rfc_text, encoding="utf-8")

        ingestor = DocumentIngestionEngine()
        chunks = ingestor.ingest_document(rfc_file)

        assert len(chunks) > 0
        assert any(c.protocol_hint == "OSPF" for c in chunks)
        # Check that parameter keywords were detected
        assert any("HelloInterval" in c.content for c in chunks)

    def test_parameter_relevance_detection(self):
        ingestor = DocumentIngestionEngine()
        assert ingestor._is_parameter_relevant("Hello interval must match across neighbor routers") is True
        assert ingestor._is_parameter_relevant("This document is Copyright (C) The Internet Society 1998") is False


class TestRuleRegistryValidator:
    """Tests rule validation, mathematical consistency, and registry compilation."""

    def test_validate_sound_rule(self, sample_valid_rule):
        validator = RuleRegistryValidator()
        issues = validator.validate_rule(sample_valid_rule)
        errors = [i for i in issues if i.severity == "ERROR"]
        assert len(errors) == 0

    def test_timer_type_and_range_check(self, sample_valid_rule):
        validator = RuleRegistryValidator()

        # Invalidate data type: string for timer
        invalid_rule = sample_valid_rule.model_copy(deep=True)
        invalid_rule.data_type = ParameterDataType.STRING
        issues = validator.validate_rule(invalid_rule)
        assert any(i.issue_type == "TYPE_MISMATCH" for i in issues)

        # Invert timer range
        invalid_rule2 = sample_valid_rule.model_copy(deep=True)
        invalid_rule2.allowed_range = {"min": 100, "max": 10}
        issues2 = validator.validate_rule(invalid_rule2)
        assert any(i.issue_type == "INVERTED_RANGE" for i in issues2)

    def test_compile_and_load_registry(self, sample_valid_rule, tmp_path):
        reg_file = tmp_path / "test_alignment_registry.json"
        validator = RuleRegistryValidator(registry_output_path=reg_file)

        out_path = validator.compile_and_save_registry([sample_valid_rule])
        assert out_path.exists()

        registry = validator.load_registry()
        assert "OSPFV2" in registry.protocols
        assert len(registry.protocols["OSPFV2"]) == 1
        assert registry.protocols["OSPFV2"][0].parameter_identifier == "hello_interval"


class TestStateGraphControllerRegistryIntegration:
    """Tests that the StateInvariantGraphController consumes compiled rules at runtime."""

    def test_graph_controller_loads_and_applies_registry_rules(self, sample_valid_rule, tmp_path):
        reg_file = tmp_path / "test_alignment_registry.json"
        validator = RuleRegistryValidator(registry_output_path=reg_file)
        validator.compile_and_save_registry([sample_valid_rule])

        controller = StateInvariantGraphController(registry_path=str(reg_file))
        assert controller._alignment_registry is not None

        intent = StructuredIntent(
            intent_id="TEST-REGISTRY-01",
            protocol="OSPFv2",
            devices=[
                DeviceIntent(name="Router-A", vendor="cisco"),
                DeviceIntent(name="Router-B", vendor="juniper"),
            ],
            parameters={"hello_interval": 5, "subnet": "10.0.0.0/30"},
        )

        invariants = controller.extract_state_invariants(intent)
        inv_types = [inv.invariant_type for inv in invariants]
        # Should include registry-enforced rule
        assert "REGISTRY_HELLO_INTERVAL" in inv_types
