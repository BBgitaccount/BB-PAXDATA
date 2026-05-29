import re
import sqlite3

import spacy


# 1. Turkish lowercasing
def turkish_lower(text: str) -> str:
    mapped = []
    for char in text:
        if char == "I":
            mapped.append("ı")
        elif char == "İ":
            mapped.append("i")
        else:
            mapped.append(char.lower())
    return "".join(mapped)


# 2. Demand category classification
def classify_demand_category(sentence_text: str) -> str:
    sentence_lower = turkish_lower(sentence_text)
    if any(
        k in sentence_lower
        for k in ["reform", "institution", "restructure", "kurumsal", "reformu"]
    ):
        return "INSTITUTIONAL_REFORM"
    if any(
        k in sentence_lower
        for k in [
            "security",
            "military",
            "force",
            "defense",
            "güvenlik",
            "askeri",
            "savunma",
            "operasyon",
            "saldırı",
            "terör",
        ]
    ):
        return "SECURITY_ACTION"
    if any(
        k in sentence_lower
        for k in [
            "economic",
            "trade",
            "finance",
            "cooperation",
            "investment",
            "ekonomi",
            "ticaret",
            "finans",
            "yatırım",
        ]
    ):
        return "ECONOMIC_COOPERATION"
    if any(
        k in sentence_lower
        for k in ["humanitarian", "aid", "refugee", "insani", "yardım", "mülteci"]
    ):
        return "HUMANITARIAN_RESPONSE"
    if any(
        k in sentence_lower
        for k in [
            "legal",
            "court",
            "accountability",
            "law",
            "hukuki",
            "mahkeme",
            "adalet",
        ]
    ):
        return "LEGAL_ACCOUNTABILITY"
    return "DIPLOMATIC_ENGAGEMENT"


# 3. Load Spacy Models
try:
    nlp_tr = spacy.load("tr_core_news_md")
except Exception:
    print(
        "Warning: tr_core_news_md not found, falling back to simple token-based extraction."
    )
    nlp_tr = None

try:
    nlp_en = spacy.load("en_core_web_sm")
except Exception:
    print(
        "Warning: en_core_web_sm not found, falling back to simple token-based extraction."
    )
    nlp_en = None


def detect_language(text: str) -> str:
    tr_chars = set("ışğçöüİIĞÜŞÖÇı")
    if any(c in tr_chars for c in text):
        return "tr"
    return "en"


# 4. Target entity extraction
def extract_target_entity(
    sentence_text: str, speaker_name: str, country: str
) -> str | None:
    lang = detect_language(sentence_text)
    nlp = nlp_tr if lang == "tr" else nlp_en
    if not nlp:
        nlp = nlp_en or nlp_tr

    entities = []
    if nlp:
        try:
            doc = nlp(sentence_text)
            for ent in doc.ents:
                entities.append({"text": ent.text, "label": ent.label_})
        except Exception as e:
            print(f"Error parsing sentence with spaCy: {e}")

    # Fallback/Supplemental check using gazetteer terms
    gazetteer = {
        "BM",
        "Birleşmiş Milletler",
        "United Nations",
        "UN",
        "AB",
        "Avrupa Birliği",
        "European Union",
        "EU",
        "NATO",
        "OECD",
        "IMF",
        "İMF",
        "G20",
        "G7",
        "OSCE",
        "AGİT",
        "Türkiye",
        "Ankara",
        "İstanbul",
        "Greece",
        "Yunanistan",
        "Syria",
        "Suriye",
        "Ukraine",
        "Ukrayna",
        "Russia",
        "Rusya",
        "US",
        "USA",
        "ABD",
        "America",
        "Amerika",
        "Somalia",
        "Somali",
    }

    sentence_lower = sentence_text.lower()
    for term in gazetteer:
        if re.search(r"\b" + re.escape(term.lower()) + r"\b", sentence_lower):
            if not any(e["text"].lower() == term.lower() for e in entities):
                entities.append(
                    {
                        "text": term,
                        "label": (
                            "GPE"
                            if term
                            not in [
                                "BM",
                                "UN",
                                "AB",
                                "EU",
                                "NATO",
                                "IMF",
                                "İMF",
                                "OECD",
                            ]
                            else "ORG"
                        ),
                    }
                )

    speaker_lower = speaker_name.lower().strip()
    country_lower = country.lower().strip()
    exclude_terms = {
        "we",
        "us",
        "our",
        "me",
        "my",
        "i",
        "biz",
        "bize",
        "bizim",
        "ben",
        "bana",
        "benim",
        "the",
    }

    targets = []
    for ent in entities:
        ent_text = ent["text"].strip()
        if not ent_text or len(ent_text) > 50:
            continue
        ent_lower = ent_text.lower()
        if ent_lower in exclude_terms:
            continue
        if speaker_lower in ent_lower or ent_lower in speaker_lower:
            continue
        if country_lower in ent_lower or ent_lower in country_lower:
            continue

        if ent["label"] in ("GPE", "ORG", "ORGANIZATION", "LOC", "LOCATION"):
            if ent_text not in targets:
                targets.append(ent_text)

    if targets:
        return ", ".join(targets)
    return None


# 5. Heal a specific database
def heal_db(db_path: str):
    print(f"\nHealing database: {db_path}...")
    try:
        conn = sqlite3.connect(db_path)
        c = conn.cursor()

        c.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='demand_records'"
        )
        if not c.fetchone():
            print(f"Table 'demand_records' does not exist in {db_path}. Skipping.")
            conn.close()
            return

        c.execute(
            "SELECT demand_id, sent_id, speaker_name, country, full_sentence FROM demand_records"
        )
        rows = c.fetchall()
        print(f"Found {len(rows)} demand records.")

        updated_count = 0
        for r in rows:
            demand_id, sent_id, speaker_name, country, full_sentence = r

            category = classify_demand_category(full_sentence)
            target = extract_target_entity(full_sentence, speaker_name, country)

            c.execute(
                "UPDATE demand_records SET demand_category = ?, target_entity = ? WHERE demand_id = ?",
                (category, target, demand_id),
            )

            if sent_id:
                c.execute(
                    "UPDATE sentences SET demand_category = ? WHERE sent_id = ?",
                    (category, sent_id),
                )

            updated_count += 1

        conn.commit()
        print(f"Successfully updated {updated_count} records in {db_path}.")
        conn.close()
    except Exception as e:
        print(f"Error healing database {db_path}: {e}")


if __name__ == "__main__":
    heal_db("bb-paxdata.db")
    heal_db("bb-paxdata-temp.db")
