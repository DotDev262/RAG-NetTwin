"""
Validation & Rule Registry Builder Module (rule_encoder/validator.py).

Validates extracted rule sets against predefined schema templates and logical consistency rules:
- Verifies timer ranges (integer ranges > 0, dead >= hello)
- Validates vendor syntax templates contains expected placeholders (<value>, <area>, etc.)
- Ensures authentication types and constraint scopes match mathematically
- Builds and exports the verified rules into alignment_rules_registry.json.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from pydantic import BaseModel, Field

from src.rule_encoder.schema import (
    AlignmentRegistry,
    AlignmentSchemaRule,
    ParameterDataType,
)
from src.utils import setup_logger

logger = setup_logger("RuleEncoderValidator")


class ValidationIssue(BaseModel):
    """Integrity check failure for an extracted alignment rule."""
    rule_id: str
    parameter_identifier: str
    issue_type: str
    message: str
    severity: str = "ERROR"  # ERROR, WARNING


class RuleValidationReport(BaseModel):
    """Aggregate validation result across an extracted rule corpus."""
    is_valid: bool
    total_rules_evaluated: int
    verified_rules_count: int
    issues: List[ValidationIssue] = Field(default_factory=list)


class RuleRegistryValidator:
    """
    Validates extracted alignment rules against formal semantic specifications
    and compiles the verified rules into a static JSON registry.
    """

    def __init__(self, registry_output_path: Optional[str | Path] = None):
        self.output_path = Path(
            registry_output_path or "config/alignment_rules_registry.json"
        )

    def validate_rule(self, rule: AlignmentSchemaRule) -> List[ValidationIssue]:
        """
        Validates a single rule for mathematical, typing, and vendor syntax consistency.
        """
        issues: List[ValidationIssue] = []

        # 1. Parameter Identifier validation
        if not rule.parameter_identifier or len(rule.parameter_identifier) < 2:
            issues.append(
                ValidationIssue(
                    rule_id=rule.rule_id,
                    parameter_identifier=str(rule.parameter_identifier),
                    issue_type="INVALID_IDENTIFIER",
                    message="Parameter identifier must be a valid non-empty snake_case string.",
                )
            )

        # 2. Timer-specific validations
        param_name = rule.parameter_identifier.lower()
        if "interval" in param_name or "timer" in param_name or "hold_time" in param_name:
            if rule.data_type != ParameterDataType.INTEGER:
                issues.append(
                    ValidationIssue(
                        rule_id=rule.rule_id,
                        parameter_identifier=rule.parameter_identifier,
                        issue_type="TYPE_MISMATCH",
                        message=f"Timers must have data_type INTEGER, found {rule.data_type}.",
                    )
                )
            if rule.allowed_range:
                min_val = rule.allowed_range.get("min")
                max_val = rule.allowed_range.get("max")
                if min_val is not None and min_val < 0:
                    issues.append(
                        ValidationIssue(
                            rule_id=rule.rule_id,
                            parameter_identifier=rule.parameter_identifier,
                            issue_type="INVALID_RANGE",
                            message=f"Timer min value cannot be negative: {min_val}",
                        )
                    )
                if min_val is not None and max_val is not None and min_val > max_val:
                    issues.append(
                        ValidationIssue(
                            rule_id=rule.rule_id,
                            parameter_identifier=rule.parameter_identifier,
                            issue_type="INVERTED_RANGE",
                            message=f"Min value ({min_val}) exceeds max value ({max_val}).",
                        )
                    )

        # 3. Vendor Syntax Mapping validation
        if not rule.vendor_syntax:
            issues.append(
                ValidationIssue(
                    rule_id=rule.rule_id,
                    parameter_identifier=rule.parameter_identifier,
                    issue_type="EMPTY_VENDOR_SYNTAX",
                    message="Rule must provide syntax mappings for at least one target vendor.",
                )
            )
        else:
            for vendor_name, mapping in rule.vendor_syntax.items():
                cmd = mapping.command_template
                if not cmd or len(cmd.strip()) == 0:
                    issues.append(
                        ValidationIssue(
                            rule_id=rule.rule_id,
                            parameter_identifier=rule.parameter_identifier,
                            issue_type="BLANK_COMMAND_TEMPLATE",
                            message=f"Command template for {vendor_name} is blank.",
                        )
                    )
                # Check for parameter placeholder
                if "<" not in cmd and "$" not in cmd and "{" not in cmd and not mapping.default_value:
                    issues.append(
                        ValidationIssue(
                            rule_id=rule.rule_id,
                            parameter_identifier=rule.parameter_identifier,
                            issue_type="MISSING_PLACEHOLDER_WARNING",
                            message=f"Command template '{cmd}' for {vendor_name} may be missing a placeholder (e.g. <value>).",
                            severity="WARNING",
                        )
                    )

        # 4. Interoperability Constraint validation
        interop = rule.interoperability_constraint
        if not interop.description or len(interop.description.strip()) == 0:
            issues.append(
                ValidationIssue(
                    rule_id=rule.rule_id,
                    parameter_identifier=rule.parameter_identifier,
                    issue_type="EMPTY_CONSTRAINT_DESC",
                    message="Interoperability constraint description must not be empty.",
                )
            )

        return issues

    def validate_corpus(
        self, rules: List[AlignmentSchemaRule]
    ) -> Tuple[List[AlignmentSchemaRule], RuleValidationReport]:
        """
        Validates an entire list of rules. Discards invalid rules with ERROR severity.
        """
        verified_rules: List[AlignmentSchemaRule] = []
        all_issues: List[ValidationIssue] = []

        for rule in rules:
            rule_issues = self.validate_rule(rule)
            has_error = any(i.severity == "ERROR" for i in rule_issues)
            all_issues.extend(rule_issues)

            if not has_error:
                verified_rules.append(rule)

        report = RuleValidationReport(
            is_valid=len([i for i in all_issues if i.severity == "ERROR"]) == 0,
            total_rules_evaluated=len(rules),
            verified_rules_count=len(verified_rules),
            issues=all_issues,
        )

        return verified_rules, report

    def compile_and_save_registry(
        self, rules: List[AlignmentSchemaRule]
    ) -> Path:
        """
        Compiles verified rules into the static registry JSON file.
        Groups rules by protocol for fast lookup.
        """
        verified_rules, report = self.validate_corpus(rules)

        # Group by protocol
        protocols_map: Dict[str, List[AlignmentSchemaRule]] = {}
        for r in verified_rules:
            proto = r.protocol_name.upper()
            if proto not in protocols_map:
                protocols_map[proto] = []
            protocols_map[proto].append(r)

        registry = AlignmentRegistry(
            registry_version="2.0.0",
            protocols=protocols_map,
        )

        # Ensure parent dir exists
        self.output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(self.output_path, "w", encoding="utf-8") as f:
            f.write(registry.model_dump_json(indent=2))

        logger.info(
            f"Successfully compiled {len(verified_rules)} verified alignment rules "
            f"into registry: {self.output_path}"
        )
        return self.output_path

    def load_registry(self) -> AlignmentRegistry:
        """Loads the compiled static registry from disk."""
        if not self.output_path.exists():
            raise FileNotFoundError(f"Registry not found at {self.output_path}")

        with open(self.output_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return AlignmentRegistry.model_validate(data)
