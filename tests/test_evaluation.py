import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from evaluation.evaluator import Evaluator

def test_evaluation():
    """Test the Evaluator class"""
    try:
        evaluator = Evaluator()
    except ValueError as e:
        print(f"Skipping test: {e}")
        return

    test_scenarios = [
        "Configure OSPF area 0 on Router-1",
        "Block traffic from 192.168.1.100"
    ]
    
    print("Testing Evaluation Suite\n")
    print("=" * 60)
    
    try:
        evaluator.run_benchmark(test_scenarios, output_file="results/test_benchmark.json")
    except Exception as e:
        print(f"Benchmark failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_evaluation()