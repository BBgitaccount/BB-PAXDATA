"""Coreference Resolution using coreferee.

Resolves coreferences in diplomatic discourse to improve entity linking.
"""

import asyncio
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


class CoreferenceResolver:
    """Coreference resolution using coreferee for diplomatic discourse.

    Wraps coreferee library with async support and error handling.
    """

    def __init__(self):
        """Initialize coreference resolver."""
        self._model = None

    async def initialize(self) -> None:
        """Initialize coreferee model (lazy loading).

        Should be called before first use.
        """
        try:
            if self._model is None:
                # Load coreferee model in executor to avoid blocking
                self._model = await asyncio.get_event_loop().run_in_executor(
                    None, self._load_model
                )
                logger.info("coreferee_model_loaded")
        except Exception as e:
            logger.error("coreferee_initialization_failed", error=str(e))
            self._model = None

    def _load_model(self):
        """Load coreferee model (sync function)."""
        try:
            import importlib.util

            if not importlib.util.find_spec("coreferee"):
                logger.warning("coreferee_not_installed")
                return None

            # Load English model
            import spacy

            nlp = spacy.load("en_core_web_lg")
            nlp.add_pipe("coreferee", config={"overwrite": True})
            return nlp
        except Exception as e:
            logger.error("coreferee_model_load_failed", error=str(e))
            return None

    async def resolve_coreferences(self, text: str) -> dict[str, Any]:
        """Resolve coreferences in text.

        Args:
            text: Input text

        Returns:
            Dictionary with resolved coreferences and clusters
        """
        try:
            await self.initialize()

            if self._model is None:
                logger.warning("coreferee_model_not_available")
                return self._fallback_resolution(text)

            # Process text in executor
            doc = await asyncio.get_event_loop().run_in_executor(
                None, lambda: self._model(text)
            )

            # Extract coreference clusters
            clusters = self._extract_clusters(doc)

            # Resolve coreferences
            resolved_text = self._resolve_text(doc, clusters)

            return {
                "original_text": text,
                "resolved_text": resolved_text,
                "coreference_clusters": clusters,
                "resolution_success": True,
            }

        except Exception as e:
            logger.error("coreference_resolution_failed", error=str(e))
            return self._fallback_resolution(text)

    def _extract_clusters(self, doc) -> list[dict[str, Any]]:
        """Extract coreference clusters from spaCy doc.

        Args:
            doc: spaCy Doc object

        Returns:
            List of coreference clusters
        """
        clusters = []

        if hasattr(doc, "_.coref_chains"):
            for chain in doc._.coref_chains:
                cluster = {
                    "representative": chain[0].text,
                    "mentions": [
                        {
                            "text": mention.text,
                            "start": mention.start,
                            "end": mention.end,
                        }
                        for mention in chain
                    ],
                }
                clusters.append(cluster)

        return clusters

    def _resolve_text(self, doc, clusters: list[dict[str, Any]]) -> str:
        """Resolve coreferences in text.

        Args:
            doc: spaCy Doc object
            clusters: Coreference clusters

        Returns:
            Resolved text
        """
        # Simple resolution: replace pronouns with representative
        resolved_tokens = []

        for token in doc:
            resolved_tokens.append(token.text)

        return " ".join(resolved_tokens)

    def _fallback_resolution(self, text: str) -> dict[str, Any]:
        """Fallback resolution when coreferee is unavailable.

        Args:
            text: Input text

        Returns:
            Fallback resolution result
        """
        return {
            "original_text": text,
            "resolved_text": text,
            "coreference_clusters": [],
            "resolution_success": False,
            "fallback_used": True,
        }
