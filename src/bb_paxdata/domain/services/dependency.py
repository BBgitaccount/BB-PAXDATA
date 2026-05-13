"""
Dependency Parsing Service for extraction of subject-verb-object triples.
"""

from typing import Any

from spacy.tokens import Doc, Token

from bb_paxdata.domain.models.dependency import DependencyTriple


class DependencyService:
    """
    Service to extract grammatical triples from SpaCy Doc objects.
    """

    def extract_triples(self, doc: Doc) -> list[DependencyTriple]:
        """
        Extract subject-verb-object triples from each sentence in the Doc.
        """
        triples = []
        for sent in doc.sents:
            root = self._find_root(sent)
            if not root:
                continue

            subjects = self._find_subjects(root)
            objects = self._find_objects(root)

            # If no direct subjects found, check for passive subjects
            is_passive = self._is_passive(root)

            for subj in subjects:
                for obj in objects:
                    triple = DependencyTriple(
                        sent_id="",  # To be filled by caller
                        subject_raw=self._subtree_text(subj),
                        subject_resolved=subj.text,  # To be resolved by ActorResolver
                        verb_lemma=root.lemma_,
                        object_raw=self._subtree_text(obj),
                        object_resolved=obj.text,  # To be resolved by ActorResolver
                        is_passive=is_passive,
                        is_negative=self._is_negative(root),
                        subject_head_pos=subj.pos_,
                        object_head_pos=obj.pos_,
                        verb_pos=root.pos_,
                    )
                    triples.append(triple)
        return triples

    def _find_root(self, sent: Any) -> Token | None:
        """Find the root verb of the sentence."""
        for token in sent:
            if token.dep_ == "ROOT":
                return token
        return None

    def _find_subjects(self, root: Token) -> list[Token]:
        """Find nominal or passive subjects of the root."""
        return [
            child for child in root.children if child.dep_ in ("nsubj", "nsubj:pass")
        ]

    def _find_objects(self, root: Token) -> list[Token]:
        """Find direct, indirect or oblique objects/nominals."""
        return [
            child for child in root.children if child.dep_ in ("obj", "iobj", "obl")
        ]

    def _subtree_text(self, token: Token) -> str:
        """Get the full text of the subtree rooted at this token."""
        return " ".join([t.text for t in token.subtree])

    def _is_passive(self, root: Token) -> bool:
        """Check if the verb is in passive voice."""
        return any(child.dep_ == "nsubj:pass" for child in root.children)

    def _is_negative(self, root: Token) -> bool:
        """Check for negation modifiers in the verb's children."""
        return any(child.dep_ == "neg" for child in root.children)
