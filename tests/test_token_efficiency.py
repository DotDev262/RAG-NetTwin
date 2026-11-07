"""
Tests for Token Efficiency & Distillation Optimizations in ConfigGenerator.
"""

from unittest.mock import MagicMock
import pytest
from src.rag.config_generator import ConfigGenerator
from src.schemas.intent import StructuredIntent, DeviceIntent, ActionType


def test_distill_context_token_ceiling():
    # Pass a lightweight mock vector store so Pytest doesn't load heavy HuggingFace/CrossEncoder models
    mock_store = MagicMock()
    mock_store.reorder_lost_in_the_middle.side_effect = lambda x: x
    generator = ConfigGenerator(vector_store=mock_store)

    # Create dummy chunks with repeated content
    dummy_chunks = [
        {
            "id": f"chunk_{i:03d}",
            "text": (
                f"interface GigabitEthernet0/{i}\n"
                f" ip address 10.0.{i}.1 255.255.255.0\n"
                f" ip ospf 1 area 0\n"
                f" ip ospf hello-interval 5\n"
                "This command specifies the hello interval for OSPF packets.\n"
                "CAUTION: Changing this will tear down adjacency.\n"
            ),
            "metadata": {"command_hierarchy": '["interface", "ip ospf"]'},
        }
        for i in range(20)
    ]

    # Test that distilled output respects the 800 token limit
    distilled = generator.distill_context(dummy_chunks, token_limit=800)
    
    # Token estimation: len // 3
    est_tokens = len(distilled) // 3
    assert est_tokens <= 850, f"Distilled context exceeded token ceiling: {est_tokens}"
    assert "CLI_SYNTAX:" in distilled
    assert "CRITICAL VENDOR RESTRICTIONS" in distilled


def test_token_counter_tracking():
    mock_store = MagicMock()
    mock_store.reorder_lost_in_the_middle.side_effect = lambda x: x
    generator = ConfigGenerator(vector_store=mock_store)
    assert hasattr(generator, "token_counter")
    initial_usage = generator.token_counter.get_total_usage()
    assert initial_usage.total_tokens == 0

    generator.token_counter.add_usage("test_call", prompt=150, completion=50)
    updated_usage = generator.token_counter.get_total_usage()
    assert updated_usage.prompt_tokens == 150
    assert updated_usage.completion_tokens == 50
    assert updated_usage.total_tokens == 200

