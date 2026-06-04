# tests/infrastructure/export/test_export.py
from __future__ import annotations

import xml.etree.ElementTree as ET

from bb_paxdata.infrastructure.export.gexf_builder import GEXFBuilder
from bb_paxdata.infrastructure.export.latex_utils import (
    escape_latex,
    render_latex_template,
)


def test_escape_latex():
    # Simple strings
    assert escape_latex("hello") == "hello"

    # Special characters
    assert escape_latex("hello % world") == r"hello \% world"
    assert escape_latex("hello & world") == r"hello \& world"
    assert escape_latex("hello _ world") == r"hello \_ world"

    # Backslash
    assert escape_latex(r"hello \ world") == r"hello \textbackslash{} world"

    # Combination
    assert (
        escape_latex(r"hello % & \ _ world") == r"hello \% \& \textbackslash{} \_ world"
    )


def test_render_latex_template():
    template = (
        "\\documentclass{article}\n"
        "\\begin{document}\n"
        "\\section{\\VAR{title|escape_latex}}\n"
        "\\BLOCK{for item in items}\n"
        "\\item \\VAR{item|escape_latex}\n"
        "\\BLOCK{endfor}\n"
        "\\end{document}"
    )
    context = {
        "title": "Diplomatic & Strategic Analysis",
        "items": ["First % item", "Second _ item"],
    }
    rendered = render_latex_template(template, context)

    assert "\\section{Diplomatic \\& Strategic Analysis}" in rendered
    assert "\\item First \\% item" in rendered
    assert "\\item Second \\_ item" in rendered


def test_gexf_builder():
    builder = GEXFBuilder(description="Test Network")
    builder.add_node_attribute("0", "type", "string")
    builder.add_node_attribute("1", "risk", "double")
    builder.add_edge_attribute("0", "interaction", "string")

    builder.add_node("Turkey", "Turkey", {"type": "Actor", "risk": 0.8})
    builder.add_node("Concept1", "Concept1", {"type": "Concept", "risk": 0.4})

    # Adding duplicate node should be a no-op
    builder.add_node("Turkey", "Turkey", {"type": "Actor", "risk": 0.8})

    builder.add_edge(
        "Turkey", "Concept1", weight=2.5, attributes={"interaction": "hedging"}
    )

    xml_str = builder.to_string()

    # Verify XML structure
    assert "<?xml" in xml_str

    # Parse to check validity
    root = ET.fromstring(xml_str.encode("utf-8"))
    assert root.tag.endswith("gexf")
    assert root.attrib["version"] == "1.2"

    # Find meta
    meta = root.find("{http://www.gexf.net/1.2draft}meta")
    assert meta is not None
    desc = meta.find("{http://www.gexf.net/1.2draft}description")
    assert desc is not None and desc.text == "Test Network"

    # Find graph
    graph = root.find("{http://www.gexf.net/1.2draft}graph")
    assert graph is not None
    assert graph.attrib["defaultedgetype"] == "directed"

    # Check attributes
    attrs = graph.findall("{http://www.gexf.net/1.2draft}attributes")
    assert len(attrs) == 2

    # Check nodes
    nodes = graph.find("{http://www.gexf.net/1.2draft}nodes")
    assert nodes is not None
    node_list = nodes.findall("{http://www.gexf.net/1.2draft}node")
    assert len(node_list) == 2
    assert any(
        n.attrib["id"] == "Turkey" and n.attrib["label"] == "Turkey" for n in node_list
    )

    # Check edges
    edges = graph.find("{http://www.gexf.net/1.2draft}edges")
    assert edges is not None
    edge_list = edges.findall("{http://www.gexf.net/1.2draft}edge")
    assert len(edge_list) == 1
    assert edge_list[0].attrib["source"] == "Turkey"
    assert edge_list[0].attrib["target"] == "Concept1"
    assert edge_list[0].attrib["weight"] == "2.5"
