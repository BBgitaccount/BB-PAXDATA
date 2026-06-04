# src/bb_paxdata/infrastructure/export/gexf_builder.py
from __future__ import annotations

import xml.etree.ElementTree as ET
from datetime import datetime
from xml.dom import minidom


class GEXFBuilder:
    """
    Builder pattern for generating standardized Gephi GEXF 1.2 XML networks
    for Fischer Discourse Network Analysis (DNA).
    """

    def __init__(self, description: str = "Fischer DNA Network Export") -> None:
        self.root = ET.Element(
            "gexf", {"xmlns": "http://www.gexf.net/1.2draft", "version": "1.2"}
        )

        from datetime import timezone

        # Add metadata
        self.meta = ET.SubElement(
            self.root,
            "meta",
            {"lastmodifieddate": datetime.now(timezone.utc).strftime("%Y-%m-%d")},
        )
        creator = ET.SubElement(self.meta, "creator")
        creator.text = "BB-PAXDATA Export Engine"
        desc = ET.SubElement(self.meta, "description")
        desc.text = description

        # Graph node configuration
        self.graph = ET.SubElement(
            self.root, "graph", {"defaultedgetype": "directed", "mode": "static"}
        )

        self.node_attributes: dict[str, str] = {}
        self.edge_attributes: dict[str, str] = {}
        self.node_attr_element: ET.Element | None = None
        self.edge_attr_element: ET.Element | None = None

        # Containers for nodes and edges
        self.nodes_element = ET.SubElement(self.graph, "nodes")
        self.edges_element = ET.SubElement(self.graph, "edges")

        self.added_nodes: set[str] = set()
        self.edge_count = 0

    def add_node_attribute(
        self, id_str: str, title: str, attr_type: str
    ) -> GEXFBuilder:
        """Define custom node attribute (e.g. type, risk_score)."""
        if self.node_attr_element is None:
            self.node_attr_element = ET.Element(
                "attributes", {"class": "node", "mode": "static"}
            )
            # Insert at the beginning of graph node
            self.graph.insert(0, self.node_attr_element)

        ET.SubElement(
            self.node_attr_element,
            "attribute",
            {"id": id_str, "title": title, "type": attr_type},
        )
        self.node_attributes[title] = id_str
        return self

    def add_edge_attribute(
        self, id_str: str, title: str, attr_type: str
    ) -> GEXFBuilder:
        """Define custom edge attribute (e.g. relationship_type)."""
        if self.edge_attr_element is None:
            self.edge_attr_element = ET.Element(
                "attributes", {"class": "edge", "mode": "static"}
            )
            # Insert after node attributes
            idx = 1 if self.node_attr_element is not None else 0
            self.graph.insert(idx, self.edge_attr_element)

        ET.SubElement(
            self.edge_attr_element,
            "attribute",
            {"id": id_str, "title": title, "type": attr_type},
        )
        self.edge_attributes[title] = id_str
        return self

    def add_node(
        self, node_id: str, label: str, attributes: dict | None = None
    ) -> GEXFBuilder:
        """Add node to graph if it doesn't already exist."""
        s_id = str(node_id)
        if s_id in self.added_nodes:
            return self

        node = ET.SubElement(
            self.nodes_element, "node", {"id": s_id, "label": str(label)}
        )
        self.added_nodes.add(s_id)

        if attributes:
            attvalues = ET.SubElement(node, "attvalues")
            for k, v in attributes.items():
                if k in self.node_attributes:
                    ET.SubElement(
                        attvalues,
                        "attvalue",
                        {"for": self.node_attributes[k], "value": str(v)},
                    )
        return self

    def add_edge(
        self,
        source_id: str,
        target_id: str,
        weight: float | None = None,
        attributes: dict | None = None,
    ) -> GEXFBuilder:
        """Add edge connecting two nodes."""
        self.edge_count += 1
        edge_id = f"edge_{self.edge_count}"

        attribs = {"id": edge_id, "source": str(source_id), "target": str(target_id)}
        if weight is not None:
            attribs["weight"] = str(weight)

        edge = ET.SubElement(self.edges_element, "edge", attribs)

        if attributes:
            attvalues = ET.SubElement(edge, "attvalues")
            for k, v in attributes.items():
                if k in self.edge_attributes:
                    ET.SubElement(
                        attvalues,
                        "attvalue",
                        {"for": self.edge_attributes[k], "value": str(v)},
                    )
        return self

    def to_string(self) -> str:
        """Generate XML string with formatted/indented GEXF payload."""
        raw_xml = ET.tostring(self.root, encoding="utf-8")
        reparsed = minidom.parseString(raw_xml)
        # Using toprettyxml for human readability (highly engineered export format)
        return reparsed.toprettyxml(indent="    ", encoding="utf-8").decode("utf-8")
