import os
import subprocess
from rich.console import Console
from rich.panel import Panel

console = Console()


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Update RAG-NetTwin Knowledge Graphs")
    parser.add_argument(
        "--type",
        choices=["code", "docs", "both"],
        default="both",
        help="Which graph to update",
    )
    args = parser.parse_args()

    if args.type in ["code", "both"]:
        console.print(
            Panel(
                "[bold magenta]RAG-NetTwin Codebase Graph Update[/bold magenta]\n"
                "Regenerating logic graph for src/",
                expand=False,
                border_style="magenta",
            )
        )
        # For code, we use setup_graphify and graphify update
        # This is typically AST-only and doesn't require an LLM API key
        cmd = "python setup_graphify.py && graphify update src/"
        try:
            subprocess.run(cmd, shell=True, check=True)
            console.print("[bold green]✓ Codebase Graph regenerated.[/bold green]\n")
        except subprocess.CalledProcessError as e:
            console.print(f"[bold red]✗ Codebase graph update failed: {e}[/bold red]")

    if args.type in ["docs", "both"]:
        console.print(
            Panel(
                "[bold cyan]RAG-NetTwin Network Concept Graph Update[/bold cyan]\n"
                "Extracting domain knowledge from data/graph_corpus/",
                expand=False,
                border_style="cyan",
            )
        )
        doc_graph_path = "./graphify-docs"

        # Load .env to get API keys for extraction
        from dotenv import load_dotenv

        load_dotenv()

        api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if not api_key or "your_api_key" in api_key:
            console.print(
                "[bold red]Error: No valid LLM API key found in .env![/bold red]"
            )
            console.print(
                "Please set a real GEMINI_API_KEY in your .env file to enable semantic extraction."
            )
            return

        # For documents, we use 'extract' to ensure deep semantic mapping of concepts
        cmd = f"graphify extract data/graph_corpus/ --out {doc_graph_path}"

        try:
            subprocess.run(cmd, shell=True, check=True)
            console.print(
                "[bold green]✓ Network Concept Graph generated successfully.[/bold green]"
            )
        except subprocess.CalledProcessError as e:
            console.print(f"[bold red]✗ Document extraction failed: {e}[/bold red]")

    console.print(
        Panel(
            "[bold green]GRAPH UPDATE COMPLETE[/bold green]",
            expand=False,
            border_style="green",
        )
    )


if __name__ == "__main__":
    main()
