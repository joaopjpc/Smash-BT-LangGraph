"""
export_graph_image.py — Gera imagem PNG do grafo core (com subgrafos expandidos).

Uso:
    python scripts/export_graph_image.py
    python scripts/export_graph_image.py --output meu_grafo.png
    python scripts/export_graph_image.py --no-xray
"""
from __future__ import annotations

import argparse
from pathlib import Path

from langchain_core.runnables import RunnableConfig

from app.core.graph import build_core_graph


def main():
    parser = argparse.ArgumentParser(description="Exporta imagem do grafo core")
    parser.add_argument("--output", "-o", default="diagramas/core_graph.png",
                        help="Caminho do arquivo PNG de saída")
    parser.add_argument("--no-xray", action="store_true",
                        help="Não expandir subgrafos")
    args = parser.parse_args()

    config = RunnableConfig()
    graph = build_core_graph(config)

    xray = not args.no_xray
    png_bytes = graph.get_graph(xray=xray).draw_mermaid_png()

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(png_bytes)

    print(f"Grafo exportado para: {output_path}")


if __name__ == "__main__":
    main()
