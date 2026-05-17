from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from spacy.language import Language

from spacy.tokens import Doc, Token

from bb_paxdata.domain.enums.negation_type import NegationType
from bb_paxdata.domain.models.negation_cue import NegationCue
from bb_paxdata.domain.services.negation_detector_protocol import (
    NegationDetectorProtocol,
)


class SpacyNegationDetector(NegationDetectorProtocol):
    """spaCy dependency parse tabanlı negasyon detection (Morante & Blanco 2012).

    Not: spaCy Doc objesi dışarıdan inject edilir (test edilebilirlik için).
    """

    SURFACE_CUES: frozenset[str] = frozenset(
        {
            "not",
            "n't",
            "never",
            "no",
            "none",
            "nobody",
            "nothing",
            "nowhere",
            "neither",
            "nor",
            "without",
            "hardly",
            "scarcely",
            "barely",
        }
    )

    SEMANTIC_CUES: frozenset[str] = frozenset(
        {
            "fail",
            "deny",
            "refuse",
            "reject",
            "avoid",
            "prevent",
            "lack",
            "absence",
            "decline",
            "oppose",
        }
    )

    def __init__(self, nlp: Language) -> None:
        self._nlp = nlp

    async def detect(self, text: str, sentence_id: str) -> Sequence[NegationCue]:
        doc: Doc = self._nlp(text)
        return await self.detect_with_doc(text, sentence_id, doc)

    async def detect_with_doc(
        self, text: str, sentence_id: str, doc: Doc
    ) -> Sequence[NegationCue]:
        """Existing Doc objesi ile detection yap (performans için)."""
        cues: list[NegationCue] = []

        for token in doc:
            cue = self._detect_cue(token, sentence_id)
            if cue:
                scoped_cue = await self.detect_scope(cue, doc)
                cues.append(scoped_cue)

        # Sort by cue_start
        return tuple(sorted(cues, key=lambda c: c.cue_start))

    def _detect_cue(self, token: Token, sentence_id: str) -> NegationCue | None:
        lower = token.lower_

        if lower in self.SURFACE_CUES:
            return NegationCue(
                cue_text=token.text,
                cue_start=token.idx,
                cue_end=token.idx + len(token.text),
                negation_type=NegationType.SURFACE,
                sentence_id=sentence_id,
            )

        if token.lemma_ in self.SEMANTIC_CUES:
            return NegationCue(
                cue_text=token.text,
                cue_start=token.idx,
                cue_end=token.idx + len(token.text),
                negation_type=NegationType.SEMANTIC,
                sentence_id=sentence_id,
            )

        return None

    async def detect_scope(self, cue: NegationCue, doc: Doc) -> NegationCue:
        # doc'ta cue'yu bul (cue_start üzerinden)
        cue_token: Token | None = None
        for token in doc:
            if token.idx == cue.cue_start and token.text == cue.cue_text:
                cue_token = token
                break

        if cue_token is None:
            # Fallback: cue bulunamazsa confidence düşür, scope yok
            return cue.model_copy(update={"confidence": 0.0})

        scope_indices: list[int] = []
        focus_idx: int | None = None
        neg_type = cue.negation_type
        confidence = cue.confidence

        if cue.negation_type == NegationType.SURFACE:
            # Dependency-based scope
            head = cue_token.head

            # Geniş kapsam kontrolü: head'in advcl/ccomp/xcomp child'ları var mı?
            wide_children = [
                c
                for c in head.children
                if c.dep_ in ("advcl", "ccomp", "xcomp", "relcl")
            ]
            if wide_children and head.i < cue_token.i:
                # "It is not [that they agreed]" yapıları
                scope_indices = [t.i for t in head.subtree]
                for wc in wide_children:
                    scope_indices.extend(t.i for t in wc.subtree)
                scope_indices = sorted(set(scope_indices))
                focus_idx = head.i
                neg_type = NegationType.SCOPE_WIDE
                confidence = 0.75
            else:
                # Standard syntactic scope: head subtree
                scope_indices = sorted([t.i for t in head.subtree])
                focus_idx = head.i
                neg_type = NegationType.SYNTACTIC
                confidence = 1.0

                # Focus refinement: dobj/obj varsa focus = obje
                for child in head.children:
                    if child.dep_ in ("dobj", "obj", "attr"):
                        focus_idx = child.i
                        break

        elif cue.negation_type == NegationType.SEMANTIC:
            # Semantic cue: kendi subtree'si + nesne/compl child'ları
            scope_indices = sorted([t.i for t in cue_token.subtree])
            focus_idx = cue_token.i

            for child in cue_token.children:
                if child.dep_ in ("dobj", "obj", "xcomp", "ccomp", "attr"):
                    scope_indices.extend(t.i for t in child.subtree)
                    scope_indices = sorted(set(scope_indices))
                    focus_idx = child.i
                    break
            confidence = 0.85

        # Scope text oluştur
        scope_text = (
            " ".join(doc[i].text for i in scope_indices) if scope_indices else ""
        )
        focus_text = doc[focus_idx].text if focus_idx is not None else None

        return cue.with_scope(
            indices=scope_indices,
            text=scope_text,
            focus_idx=focus_idx,
            focus_txt=focus_text,
        ).model_copy(
            update={
                "negation_type": neg_type,
                "confidence": confidence,
            }
        )
