"""
Dependency Parsing Service for extraction of subject-verb-object triples.
"""

from spacy.tokens import Doc, Token

from bb_paxdata.application.domain.models.dependency import DependencyTriple


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
            # Find all verbs or roots
            verbs = [t for t in sent if t.pos_ in ("VERB", "AUX") or t.dep_ == "ROOT"]
            for verb in verbs:
                # Find nominal or passive subjects
                subjects = [
                    c
                    for c in verb.children
                    if c.dep_ in ("nsubj", "nsubj:pass", "nsubjpass")
                ]

                # Find direct, indirect, oblique objects/nominals
                objects = [
                    c
                    for c in verb.children
                    if c.dep_ in ("obj", "iobj", "obl", "dobj", "pobj")
                ]

                # Prepositional objects (e.g. faced with choices -> with (prep) -> choices (pobj))
                prep_children = [c for c in verb.children if c.dep_ == "prep"]
                for prep in prep_children:
                    pobjs = [c for c in prep.children if c.dep_ == "pobj"]
                    objects.extend(pobjs)

                # Attributes for copulas (e.g. Syria is a bridge -> bridge (attr))
                attrs = [c for c in verb.children if c.dep_ == "attr"]
                objects.extend(attrs)

                is_passive = any(
                    c.dep_ in ("nsubj:pass", "nsubjpass", "auxpass")
                    for c in verb.children
                )
                is_negative = any(c.dep_ == "neg" for c in verb.children)

                for subj in subjects:
                    for obj in objects:
                        triple = DependencyTriple(
                            sent_id="",  # To be filled by caller
                            subject_raw=self._subtree_text(subj),
                            subject_resolved=subj.text,  # To be resolved by ActorResolver
                            verb_lemma=verb.lemma_,
                            object_raw=self._subtree_text(obj),
                            object_resolved=obj.text,  # To be resolved by ActorResolver
                            is_passive=is_passive,
                            is_negative=is_negative,
                            subject_head_pos=subj.pos_,
                            object_head_pos=obj.pos_,
                            verb_pos=verb.pos_,
                        )
                        triples.append(triple)
        return triples

    def _subtree_text(self, token: Token) -> str:
        """Get the full text of the subtree rooted at this token."""
        return " ".join([t.text for t in token.subtree])

    def _is_negative(self, root: Token) -> bool:
        """Check for negation modifiers in the verb's children."""
        return any(child.dep_ == "neg" for child in root.children)
