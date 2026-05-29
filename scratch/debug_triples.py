import asyncio

from bb_paxdata.infrastructure.container.service_container import ServiceContainer
from bb_paxdata.infrastructure.db.models import Sentence
from bb_paxdata.infrastructure.db.session import get_db as get_session


def extract_triples_enhanced(doc):
    triples = []
    for sent in doc.sents:
        # Find all verbs or roots
        verbs = [t for t in sent if t.pos_ in ("VERB", "AUX") or t.dep_ == "ROOT"]
        for verb in verbs:
            # Find subjects
            subjects = [
                c
                for c in verb.children
                if c.dep_ in ("nsubj", "nsubj:pass", "nsubjpass")
            ]

            # Find objects (direct, indirect, oblique)
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
                c.dep_ in ("nsubj:pass", "nsubjpass", "auxpass") for c in verb.children
            )
            is_negative = any(c.dep_ == "neg" for c in verb.children)

            for subj in subjects:
                for obj in objects:
                    # Construct subtree texts
                    subj_text = " ".join([t.text for t in subj.subtree])
                    obj_text = " ".join([t.text for t in obj.subtree])
                    triples.append(
                        {
                            "subject": subj_text,
                            "verb": verb.lemma_,
                            "object": obj_text,
                            "is_passive": is_passive,
                            "is_negative": is_negative,
                        }
                    )
    return triples


async def main():
    container = ServiceContainer(logic_mode=True)
    ner_service = container.ner_service

    nlp_en = ner_service._models.get("en")
    nlp_tr = ner_service._models.get("tr")

    async for session in get_session():
        from sqlalchemy import select

        res = await session.execute(select(Sentence).limit(20))
        sents = res.scalars().all()

        for s in sents:
            lang = "en"
            # simple check for turkish
            if any(
                w in s.text.lower()
                for w in ["ve", "bir", "bu", "da", "de", "için", "olan"]
            ):
                lang = "tr"
            nlp = nlp_en if lang == "en" else nlp_tr
            if not nlp:
                continue

            doc = nlp(s.text)
            triples = extract_triples_enhanced(doc)
            if triples:
                print(f"\nText: {s.text}")
                print(f"Language: {lang}")
                for t in triples:
                    print(
                        f"  S: {t['subject']:25} | V: {t['verb']:10} | O: {t['object']:25} | passive: {t['is_passive']} | neg: {t['is_negative']}"
                    )


if __name__ == "__main__":
    asyncio.run(main())
