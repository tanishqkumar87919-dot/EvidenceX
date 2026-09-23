import re
import unicodedata
from typing import List, Optional, Set, Tuple

from ...schemas.claim import (
    ClaimType,
    ExtractedClaimCandidate,
    SourcePreference,
    VerificationTaskPlan,
)
from .base import BaseLLMProvider


class LocalNLPClaimExtractor(BaseLLMProvider):
    """
    Intelligent, rule-based & regex-driven NLP claim extractor and decomposer.
    Functions 100% locally and deterministically without external LLM API dependencies.
    Extracts atomic claims, performs compound claim decomposition, classifies into 12 taxonomy
    types, extracts entities and temporal anchors, and generates verification tasks with search queries.
    """

    # Non-factual prefixes, boilerplate, and subjective indicators
    OPINION_PREFIXES = (
        "i think",
        "in my opinion",
        "in my view",
        "i believe",
        "i feel",
        "i guess",
        "it seems to me",
        "to be honest",
        "personally,",
        "as far as i know",
    )

    GREETINGS = (
        "hello",
        "hi ",
        "hi,",
        "hey ",
        "hey,",
        "dear ",
        "good morning",
        "good afternoon",
        "good evening",
        "greetings",
    )

    SIGN_OFFS = (
        "thanks",
        "thank you",
        "best regards",
        "sincerely",
        "cheers",
        "regards",
        "yours truly",
    )

    CALL_TO_ACTIONS = (
        "click here",
        "subscribe to",
        "follow us on",
        "read more at",
        "terms and conditions",
        "privacy policy",
        "all rights reserved",
        "leave a comment",
        "share this post",
        "sign up for",
    )

    # Keywords for taxonomy classification
    SCIENTIFIC_KEYWORDS = {
        "cancer", "cure", "cures", "vaccine", "vaccines", "virus", "bacteria", "covid", "covid-19",
        "dna", "rna", "gene", "telescope", "exoplanet", "atmosphere", "carbon", "quantum",
        "superposition", "entanglement", "qubits", "astronomy", "physics", "chemistry",
        "biology", "clinical trial", "study finds", "researchers", "laboratory", "temperature",
        "celsius", "fahrenheit", "freezes", "boils", "species", "evolution",
    }

    ECONOMIC_KEYWORDS = {
        "inflation", "gdp", "economy", "economic", "unemployment", "interest rate", "recession",
        "federal reserve", "central bank", "stock market", "revenue", "profit", "deficit",
        "trade deficit", "billion", "trillion", "dollar", "dollars", "euro", "euros", "currency",
        "treasury", "fiscal", "debt", "tariff",
    }

    POLITICAL_KEYWORDS = {
        "president", "prime minister", "senate", "congress", "parliament", "election",
        "voter", "voters", "legislation", "bill", "executive order", "white house",
        "kremlin", "government", "diplomat", "treaty", "ambassador", "sanctions",
        "minister", "campaign", "ballot", "democrat", "republican", "parliamentary",
    }

    ORGANIZATION_ACRONYMS = {
        "WHO", "NASA", "UN", "FBI", "CIA", "NATO", "CDC", "FDA", "IMF", "SEC",
        "EU", "WTO", "ISRO", "ESA", "NIH", "DOJ", "DOD", "EPA",
    }

    def __init__(self):
        # Precompile common regexes
        self.abbrev_regex = re.compile(r"\b(Dr|Mr|Mrs|Ms|Prof|Gov|Pres|Sen|Rep|Gen|Col|Capt|Lt|St|vs|e\.g|i\.e|etc|U\.S|U\.K|Inc|Corp|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)\.\s*", re.IGNORECASE)
        self.number_regex = re.compile(r"\b\d+([.,]\d+)?\b")
        self.percentage_regex = re.compile(r"\b\d+([.,]\d+)?\s*(%|percent)\b", re.IGNORECASE)
        self.year_regex = re.compile(r"\b(19\d\d|20\d\d)\b")
        self.date_regex = re.compile(
            r"\b((?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+\d{1,2}(?:st|nd|rd|th)?(?:,?\s+\d{4})?|\d{1,2}(?:st|nd|rd|th)?\s+(?:of\s+)?(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)(?:,?\s+\d{4})?)\b",
            re.IGNORECASE,
        )
        self.quote_regex = re.compile(r'["\u201c\u201d]([^"\u201c\u201d]{10,})["\u201c\u201d]')
        # Pattern for reporting structures with location and date:
        # e.g., "The WHO announced in Geneva on May 5th, 2023 that COVID-19 is no longer a global health emergency."
        self.reporting_compound_regex = re.compile(
            r"^(?P<subject>.+?)\s+(?P<verb>announced|declared|reported|stated|confirmed|proclaimed|signed|issued|revealed)"
            r"(?:\s+(?:in|at)\s+(?P<location>[A-Z][a-zA-Z\s]+?))?"
            r"(?:\s+(?:on|in)\s+(?P<date>(?:(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2}(?:st|nd|rd|th)?(?:,?\s+\d{4})?|\d{4})))?"
            r"\s+that\s+(?P<clause>.+)$",
            re.IGNORECASE,
        )

    async def extract_and_decompose_claims(
        self,
        text: str,
        investigation_id: str,
        language: str = "en",
    ) -> List[ExtractedClaimCandidate]:
        """
        Extracts atomic claims from text, decomposes compound claims, classifies,
        and generates verification tasks.
        """
        if not text or not text.strip():
            return []

        cleaned_text = unicodedata.normalize("NFC", text.strip())
        raw_sentences = self._split_into_sentences(cleaned_text)

        candidates: List[ExtractedClaimCandidate] = []
        seen_claim_texts: Set[str] = set()

        for sentence in raw_sentences:
            sentence = sentence.strip()
            if not self._is_factual_candidate(sentence):
                continue

            # Attempt compound decomposition
            decomposed = self._decompose_sentence(sentence)

            for atomic_claim_text in decomposed:
                norm_text = atomic_claim_text.strip()
                if len(norm_text) < 10 or norm_text.lower() in seen_claim_texts:
                    continue
                seen_claim_texts.add(norm_text.lower())

                # Classify, extract entities/dates, build tasks
                claim_type = self._classify_claim(norm_text, sentence)
                entities = self._extract_entities(norm_text)
                temporal_info = self._extract_temporal_info(norm_text)
                confidence = self._compute_extraction_confidence(norm_text, entities, temporal_info)
                tasks = self._generate_verification_tasks(norm_text, claim_type, entities, temporal_info)

                candidate = ExtractedClaimCandidate(
                    claim_text=norm_text,
                    claim_type=claim_type,
                    context=sentence,
                    extraction_confidence=confidence,
                    language=language,
                    temporal_info=temporal_info,
                    entities=entities,
                    verification_tasks=tasks,
                )
                candidates.append(candidate)

        return candidates

    def _split_into_sentences(self, text: str) -> List[str]:
        """Splits text into sentences while protecting abbreviations and numbers."""
        # Replace line breaks with spaces
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        flat_text = " ".join(lines)

        # Protect common abbreviations by temporarily replacing their period with a placeholder
        placeholder = "@@PERIOD@@"
        protected = self.abbrev_regex.sub(lambda m: m.group(0).replace(".", placeholder), flat_text)

        # Protect decimal numbers (e.g. 3.2% or 8,848.5)
        protected = re.sub(r"(\d)\.(\d)", r"\1" + placeholder + r"\2", protected)

        # Split on sentence terminals
        raw_parts = re.split(r"(?<=[.!?])\s+", protected)

        sentences = []
        for part in raw_parts:
            restored = part.replace(placeholder, ".").strip()
            if restored:
                sentences.append(restored)
        return sentences

    def _is_factual_candidate(self, sentence: str) -> bool:
        """Determines if a sentence contains a potentially verifiable factual assertion."""
        # Minimum character/word threshold
        words = sentence.split()
        if len(sentence) < 15 or len(words) < 3:
            return False

        lower = sentence.lower()

        # Filter out questions (unless containing quotation of claim)
        if sentence.endswith("?") and not ('"' in sentence or "'" in sentence):
            return False
        if lower.startswith(("what is ", "why did ", "how do ", "is it true that", "can anyone ", "who was ")):
            return False

        # Filter out greetings
        for g in self.GREETINGS:
            if lower.startswith(g):
                return False

        # Filter out sign-offs
        for s in self.SIGN_OFFS:
            if lower.startswith(s):
                return False

        # Filter out pure CTAs
        for cta in self.CALL_TO_ACTIONS:
            if cta in lower:
                return False

        # Filter out pure subjective opinion prefixes without a nested proposition
        for op in self.OPINION_PREFIXES:
            if lower.startswith(op):
                # If there is no subordinate 'that' or concrete assertion, skip
                if " that " not in lower and not self.number_regex.search(sentence):
                    return False

        return True

    def _decompose_sentence(self, sentence: str) -> List[str]:
        """
        Decomposes compound sentences into atomic, independently verifiable claims.
        """
        results: List[str] = []

        # 1. Check reporting structure with location and/or date
        # E.g. "The WHO announced in Geneva on May 5th, 2023 that COVID-19 is no longer a global health emergency."
        match = self.reporting_compound_regex.match(sentence)
        if match:
            subj = match.group("subject").strip()
            verb = match.group("verb").strip()
            loc = match.group("location").strip() if match.group("location") else None
            date_str = match.group("date").strip() if match.group("date") else None
            clause = match.group("clause").strip()

            # Ensure clause ends with a period
            if not clause.endswith("."):
                clause += "."

            # Primary claim 1: The core assertion made by the entity
            results.append(f"{subj} {verb} that {clause}")

            # Sub-claim 2: Date assertion if present
            if date_str:
                results.append(f"The announcement occurred on {date_str}.")

            # Sub-claim 3: Location assertion if present
            if loc:
                results.append(f"The announcement was made in {loc}.")

            return results

        # 2. Check coordinated clauses split by ', while ' or ', whereas '
        # E.g. "Inflation dropped by 3.2% in the UK during Q3 2023, while unemployment reached 4.1%."
        coord_split = re.split(r",\s+(?:while|whereas)\s+", sentence, flags=re.IGNORECASE)
        if len(coord_split) == 2:
            first_clause = coord_split[0].strip()
            second_clause = coord_split[1].strip()
            if not first_clause.endswith("."):
                first_clause += "."
            if not second_clause.endswith("."):
                second_clause += "."
            # Capitalize second clause
            second_clause = second_clause[0].upper() + second_clause[1:]
            results.append(first_clause)
            results.append(second_clause)
            return results

        # 3. Check for direct quotes
        # E.g., 'Dr. Smith stated: "The treatment is 90% effective in mice."'
        quote_match = self.quote_regex.search(sentence)
        if quote_match:
            quote_text = quote_match.group(1).strip()
            # If quote contains distinct proposition
            if len(quote_text) > 15:
                results.append(sentence)
                return results

        # Default: single atomic claim
        results.append(sentence)
        return results

    def _classify_claim(self, claim_text: str, context: str) -> ClaimType:
        """Classifies an atomic claim into one of the 12 ClaimType categories."""
        lower = claim_text.lower()
        words = set(re.findall(r"\b\w+\b", lower))

        # Check for specific temporal assertions
        if claim_text.startswith("The announcement occurred on") or (
            self.date_regex.search(claim_text) and ("occurred" in lower or "took place" in lower or "date" in lower)
        ):
            return ClaimType.DATE

        # Check for location assertions
        if claim_text.startswith("The announcement was made in") or (
            ("in " in lower or "at " in lower) and ("located" in lower or "held in" in lower or "made in" in lower)
        ):
            return ClaimType.LOCATION

        # Check for statistics/numbers
        if self.percentage_regex.search(claim_text) or any(
            kw in lower for kw in ("increased by", "decreased by", "rose to", "fell to", "total of", "percent")
        ):
            return ClaimType.STATISTIC

        # Check for quotes
        if ('"' in claim_text or "\u201c" in claim_text) or any(
            kw in lower for kw in ("said that", "stated that", "quoted as saying")
        ):
            return ClaimType.QUOTE

        # Check for scientific / medical
        if bool(words & self.SCIENTIFIC_KEYWORDS):
            return ClaimType.SCIENTIFIC

        # Check for economic / financial
        if bool(words & self.ECONOMIC_KEYWORDS):
            return ClaimType.ECONOMIC

        # Check for political / governmental
        if bool(words & self.POLITICAL_KEYWORDS):
            return ClaimType.POLITICAL

        # Check for prominent organizations
        for org in self.ORGANIZATION_ACRONYMS:
            if re.search(rf"\b{org}\b", claim_text):
                return ClaimType.ORGANIZATION

        # Check for product / tech
        if any(kw in lower for kw in ("product", "smartphone", "device", "features", "released", "launch of", "specifications")):
            return ClaimType.PRODUCT

        # Check for event
        if any(kw in lower for kw in ("crash", "incident", "announced", "declared", "protest", "summit", "conference", "meeting")):
            return ClaimType.EVENT

        # Check for person
        if any(kw in lower for kw in ("dr.", "president", "ceo", "author", "minister")):
            return ClaimType.PERSON

        return ClaimType.OTHER

    def _extract_entities(self, text: str) -> List[str]:
        """Extracts candidate named entities (capitalized multi-word tokens or acronyms)."""
        entities: List[str] = []
        # Find acronyms
        for token in text.split():
            clean = token.strip(".,;:\"'()[]{}")
            if clean in self.ORGANIZATION_ACRONYMS and clean not in entities:
                entities.append(clean)

        # Find capitalized phrases (2-4 words)
        cap_matches = re.findall(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b", text)
        for m in cap_matches:
            if m not in entities and len(m) > 3:
                entities.append(m)

        # Single capitalized words of importance
        single_caps = re.findall(r"\b([A-Z][a-zA-Z0-9_-]+)\b", text)
        for sc in single_caps:
            if sc not in entities and sc not in ("The", "This", "That", "When", "What", "There", "Here", "It", "In", "On", "At", "A", "An"):
                entities.append(sc)

        return entities[:6]

    def _extract_temporal_info(self, text: str) -> Optional[str]:
        """Extracts temporal expressions from text."""
        date_m = self.date_regex.search(text)
        if date_m:
            return date_m.group(0).strip()
        year_m = self.year_regex.search(text)
        if year_m:
            return year_m.group(0).strip()
        return None

    def _compute_extraction_confidence(
        self,
        claim_text: str,
        entities: List[str],
        temporal_info: Optional[str],
    ) -> float:
        """
        Computes extraction confidence (0.0 to 1.0) indicating certainty
        that this proposition constitutes a verifiable factual claim.
        """
        confidence = 0.75
        if entities:
            confidence += 0.08
        if temporal_info:
            confidence += 0.06
        if self.number_regex.search(claim_text):
            confidence += 0.06
        if any(v in claim_text.lower() for v in ("announced", "declared", "found", "detected", "measured", "reported")):
            confidence += 0.04

        return min(round(confidence, 2), 0.98)

    def _generate_verification_tasks(
        self,
        claim_text: str,
        claim_type: ClaimType,
        entities: List[str],
        temporal_info: Optional[str],
    ) -> List[VerificationTaskPlan]:
        """
        Generates 1 to 2 targeted verification tasks with future search queries
        and recommended source preferences.
        """
        tasks: List[VerificationTaskPlan] = []

        # Formulate primary verification question
        clean_text = claim_text.rstrip(".")
        if clean_text.lower().startswith("the announcement occurred on"):
            date_val = clean_text.split(" on ")[-1]
            question = f"Did this official announcement take place on {date_val}?"
            query = f"official announcement date {date_val} verification"
            source_prefs = [SourcePreference.PRIMARY_SOURCE, SourcePreference.REPUTABLE_NEWS]
        elif clean_text.lower().startswith("the announcement was made in"):
            loc_val = clean_text.split(" in ")[-1]
            question = f"Was this official announcement held in {loc_val}?"
            query = f"official announcement location {loc_val} verification"
            source_prefs = [SourcePreference.PRIMARY_SOURCE, SourcePreference.REPUTABLE_NEWS]
        else:
            # General factual question
            question = f"Is it factually accurate that {clean_text[0].lower() + clean_text[1:]}?"
            # Build search query by combining key entities, temporal anchor, and claim tokens
            query_tokens = []
            if entities:
                query_tokens.extend(entities[:3])
            if temporal_info:
                query_tokens.append(temporal_info)

            # Add salient content terms
            words = [w for w in re.findall(r"\b[A-Za-z0-9-]+\b", clean_text) if len(w) > 3 and w.lower() not in (
                "that", "with", "from", "this", "have", "were", "been", "there", "their", "about"
            )]
            for w in words[:4]:
                if w not in query_tokens:
                    query_tokens.append(w)

            query = " ".join(query_tokens[:8])

            # Assign source preferences based on taxonomy
            if claim_type in (ClaimType.SCIENTIFIC,):
                source_prefs = [SourcePreference.ACADEMIC, SourcePreference.OFFICIAL]
            elif claim_type in (ClaimType.STATISTIC, ClaimType.ECONOMIC):
                source_prefs = [SourcePreference.OFFICIAL, SourcePreference.GOVERNMENT, SourcePreference.REPUTABLE_NEWS]
            elif claim_type in (ClaimType.POLITICAL, ClaimType.EVENT):
                source_prefs = [SourcePreference.REPUTABLE_NEWS, SourcePreference.GOVERNMENT, SourcePreference.FACT_CHECK]
            elif claim_type in (ClaimType.ORGANIZATION, ClaimType.QUOTE):
                source_prefs = [SourcePreference.PRIMARY_SOURCE, SourcePreference.OFFICIAL, SourcePreference.REPUTABLE_NEWS]
            else:
                source_prefs = [SourcePreference.REPUTABLE_NEWS, SourcePreference.FACT_CHECK]

        tasks.append(
            VerificationTaskPlan(
                task_description=question,
                search_query=query,
                source_preferences=source_prefs,
                task_status="pending",
            )
        )

        return tasks
