"""RST Discourse Parser - Rhetorical Structure Theory analysis.

Implements lexical-based RST parsing with optional LLM fallback.
"""

from typing import Any

import structlog

logger = structlog.get_logger(__name__)


class RSTRelation:
    """RST relation type."""

    ELABORATION = "elaboration"
    EXPLANATION = "explanation"
    CONTRAST = "contrast"
    CONCESSION = "concession"
    CAUSE = "cause"
    RESULT = "result"
    CONDITION = "condition"
    PURPOSE = "purpose"
    JOINT = "joint"
    SEQUENCE = "sequence"


class RSTNode:
    """RST tree node."""

    def __init__(
        self,
        text: str,
        relation: str,
        nuclearity: str,  # "nucleus" or "satellite"
        children: list["RSTNode"] | None = None,
    ):
        self.text = text
        self.relation = relation
        self.nuclearity = nuclearity
        self.children = children or []


class RSTDiscourseParser:
    """RST discourse parser for diplomatic discourse.

    Implements lexical-based parsing with optional LLM fallback.
    """

    # Lexical markers for RST relations
    LEXICAL_MARKERS = {
        RSTRelation.ELABORATION: [
            "specifically",
            "for example",
            "such as",
            "namely",
            "in particular",
            "that is",
        ],
        RSTRelation.EXPLANATION: [
            "because",
            "since",
            "as",
            "due to",
            "for this reason",
            "therefore",
        ],
        RSTRelation.CONTRAST: [
            "however",
            "but",
            "although",
            "nevertheless",
            "on the other hand",
            "conversely",
        ],
        RSTRelation.CONCESSION: [
            "although",
            "despite",
            "even though",
            "while",
            "admittedly",
        ],
        RSTRelation.CAUSE: [
            "because",
            "since",
            "as",
            "due to",
            "owing to",
        ],
        RSTRelation.RESULT: [
            "therefore",
            "thus",
            "consequently",
            "as a result",
            "hence",
        ],
        RSTRelation.CONDITION: [
            "if",
            "unless",
            "provided that",
            "in case",
            "assuming",
        ],
        RSTRelation.PURPOSE: [
            "in order to",
            "to",
            "so that",
            "for the purpose of",
        ],
        RSTRelation.JOINT: [
            "and",
            "also",
            "moreover",
            "furthermore",
            "in addition",
        ],
        RSTRelation.SEQUENCE: [
            "first",
            "second",
            "then",
            "next",
            "finally",
            "subsequently",
        ],
    }

    def __init__(self, use_llm_fallback: bool = False):
        """Initialize RST discourse parser.

        Args:
            use_llm_fallback: Whether to use LLM for complex cases
        """
        self.use_llm_fallback = use_llm_fallback

    async def parse_discourse(self, text: str) -> dict[str, Any]:
        """Parse discourse structure using RST.

        Args:
            text: Input text

        Returns:
            Parsed discourse structure with RST tree
        """
        try:
            # Split into sentences
            sentences = self._split_sentences(text)

            # Build RST tree using lexical markers
            rst_tree = await self._build_lexical_rst_tree(sentences)

            # If LLM fallback enabled and tree is ambiguous, use LLM
            if self.use_llm_fallback and self._is_ambiguous(rst_tree):
                rst_tree = await self._llm_rst_parse(text)

            return {
                "original_text": text,
                "rst_tree": self._tree_to_dict(rst_tree),
                "relation_counts": self._count_relations(rst_tree),
                "nuclearity_distribution": self._count_nuclearity(rst_tree),
                "parsing_method": "lexical" if not self.use_llm_fallback else "hybrid",
            }

        except Exception as e:
            logger.error("rst_parsing_failed", error=str(e))
            return self._fallback_parse(text)

    def _split_sentences(self, text: str) -> list[str]:
        """Split text into sentences.

        Args:
            text: Input text

        Returns:
            List of sentences
        """
        # Simple sentence splitting
        import re

        sentences = re.split(r"[.!?]+", text)
        return [s.strip() for s in sentences if s.strip()]

    async def _build_lexical_rst_tree(self, sentences: list[str]) -> RSTNode:
        """Build RST tree using lexical markers.

        Args:
            sentences: List of sentences

        Returns:
            Root RST node
        """
        # Build tree bottom-up
        nodes = [RSTNode(s, "text", "nucleus") for s in sentences]

        # Merge nodes based on lexical markers
        while len(nodes) > 1:
            # Find best relation between adjacent nodes
            best_relation = None
            best_score = 0.0
            best_idx = 0

            for i in range(len(nodes) - 1):
                relation, score = self._detect_relation(
                    nodes[i].text, nodes[i + 1].text
                )
                if score > best_score:
                    best_relation = relation
                    best_score = score
                    best_idx = i

            if best_relation and best_score > 0.3:
                # Merge nodes
                merged = RSTNode(
                    text=nodes[best_idx].text + " " + nodes[best_idx + 1].text,
                    relation=best_relation,
                    nuclearity="nucleus",
                    children=[nodes[best_idx], nodes[best_idx + 1]],
                )
                nodes[best_idx] = merged
                nodes.pop(best_idx + 1)
            else:
                # Default to joint relation
                merged = RSTNode(
                    text=nodes[0].text + " " + nodes[1].text,
                    relation=RSTRelation.JOINT,
                    nuclearity="nucleus",
                    children=[nodes[0], nodes[1]],
                )
                nodes[0] = merged
                nodes.pop(1)

        return nodes[0] if nodes else RSTNode("", "text", "nucleus")

    def _detect_relation(self, text1: str, text2: str) -> tuple[str, float]:
        """Detect RST relation between two text segments.

        Args:
            text1: First text segment
            text2: Second text segment

        Returns:
            Tuple of (relation, confidence_score)
        """
        # Check for lexical markers
        combined = text1.lower() + " " + text2.lower()

        best_relation = RSTRelation.JOINT
        best_score = 0.0

        for relation, markers in self.LEXICAL_MARKERS.items():
            for marker in markers:
                if marker in combined:
                    # Simple scoring based on marker presence
                    score = 0.5
                    if score > best_score:
                        best_relation = relation
                        best_score = score

        return best_relation, best_score

    async def _llm_rst_parse(self, text: str) -> RSTNode:
        """Use LLM for RST parsing (optional fallback).

        Args:
            text: Input text

        Returns:
            RST node from LLM parsing
        """
        # Placeholder for LLM integration
        # Would call an LLM API to get RST structure
        logger.info("llm_rst_parse_called", text_length=len(text))
        return await self._build_lexical_rst_tree(self._split_sentences(text))

    def _is_ambiguous(self, tree: RSTNode) -> bool:
        """Check if RST tree is ambiguous.

        Args:
            tree: RST tree

        Returns:
            True if ambiguous
        """
        # Simple heuristic: if many joint relations, consider ambiguous
        joint_count = self._count_relations(tree).get(RSTRelation.JOINT, 0)
        return joint_count > len(self._count_relations(tree)) * 0.5

    def _tree_to_dict(self, node: RSTNode) -> dict[str, Any]:
        """Convert RST tree to dictionary.

        Args:
            node: RST node

        Returns:
            Dictionary representation
        """
        return {
            "text": node.text,
            "relation": node.relation,
            "nuclearity": node.nuclearity,
            "children": [self._tree_to_dict(child) for child in node.children],
        }

    def _count_relations(self, node: RSTNode) -> dict[str, int]:
        """Count relations in RST tree.

        Args:
            node: RST node

        Returns:
            Dictionary of relation counts
        """
        counts = {node.relation: 1}
        for child in node.children:
            child_counts = self._count_relations(child)
            for relation, count in child_counts.items():
                counts[relation] = counts.get(relation, 0) + count
        return counts

    def _count_nuclearity(self, node: RSTNode) -> dict[str, int]:
        """Count nuclearity in RST tree.

        Args:
            node: RST node

        Returns:
            Dictionary of nuclearity counts
        """
        counts = {node.nuclearity: 1}
        for child in node.children:
            child_counts = self._count_nuclearity(child)
            for nuclearity, count in child_counts.items():
                counts[nuclearity] = counts.get(nuclearity, 0) + count
        return counts

    def _fallback_parse(self, text: str) -> dict[str, Any]:
        """Fallback parsing when RST parsing fails.

        Args:
            text: Input text

        Returns:
            Fallback parse result
        """
        sentences = self._split_sentences(text)
        return {
            "original_text": text,
            "rst_tree": {
                "text": text,
                "relation": "text",
                "nuclearity": "nucleus",
                "children": [],
            },
            "relation_counts": {"text": len(sentences)},
            "nuclearity_distribution": {"nucleus": len(sentences)},
            "parsing_method": "fallback",
        }
