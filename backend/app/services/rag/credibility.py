import urllib.parse
from dataclasses import dataclass
from typing import Optional


@dataclass
class SourceAssessment:
    """Credibility signal and category for an evidence source."""
    domain: str
    source_type: str
    credibility_weight: float
    publisher: Optional[str] = None
    is_known_fact_checker: bool = False
    is_academic: bool = False
    is_government: bool = False


class SourceCredibilityEvaluator:
    """
    Evaluates source domain authority and assigns standardized source categories.
    Categories serve as soft evidence ranking signals, not absolute truth proof.
    """

    GOVERNMENT_TLDS = {".gov", ".mil", ".nic.in", ".gov.uk", ".gov.au", ".europa.eu"}
    ACADEMIC_DOMAINS = {
        "arxiv.org", "nature.com", "science.org", "sciencedirect.com",
        "nih.gov", "ncbi.nlm.nih.gov", "springer.com", "ieee.org",
        "acm.org", "pnas.org", "cell.com", "thelancet.com", "jstor.org"
    }
    ACADEMIC_TLDS = {".edu", ".ac.uk", ".edu.au", ".res.in"}

    FACT_CHECK_DOMAINS = {
        "snopes.com", "politifact.com", "factcheck.org", "reuters.com/fact-check",
        "apnews.com/hub/ap-fact-check", "fullfact.org", "altnews.in", "boomlive.in"
    }

    REPUTABLE_NEWS_DOMAINS = {
        "reuters.com", "apnews.com", "bbc.com", "bbc.co.uk", "nytimes.com",
        "wsj.com", "bloomberg.com", "theguardian.com", "washingtonpost.com",
        "ft.com", "economist.com", "npr.org", "afp.com", "aljazeera.com"
    }

    OFFICIAL_ORGANIZATIONS = {
        "nasa.gov", "who.int", "un.org", "cdc.gov", "fda.gov",
        "wmo.int", "worldbank.org", "imf.org", "unesco.org", "esa.int", "isro.gov.in"
    }

    def assess_source(self, url: str, publisher: Optional[str] = None) -> SourceAssessment:
        if not url:
            return SourceAssessment(domain="", source_type="OTHER", credibility_weight=0.50)

        domain = urllib.parse.urlparse(url).netloc.lower()
        if domain.startswith("www."):
            domain = domain[4:]

        # 1. Official International / Agency Organizations
        if any(org in domain for org in self.OFFICIAL_ORGANIZATIONS):
            return SourceAssessment(
                domain=domain,
                source_type="OFFICIAL",
                credibility_weight=0.95,
                publisher=publisher or domain,
                is_government=True,
            )

        # 2. Government Portals
        if any(domain.endswith(tld) for tld in self.GOVERNMENT_TLDS):
            return SourceAssessment(
                domain=domain,
                source_type="GOVERNMENT",
                credibility_weight=0.95,
                publisher=publisher or domain,
                is_government=True,
            )

        # 3. Academic Institutions & Journals
        if any(acad in domain for acad in self.ACADEMIC_DOMAINS) or any(domain.endswith(tld) for tld in self.ACADEMIC_TLDS):
            return SourceAssessment(
                domain=domain,
                source_type="ACADEMIC",
                credibility_weight=0.95,
                publisher=publisher or domain,
                is_academic=True,
            )

        # 4. Verified Fact Checking Organizations
        url_lower = url.lower()
        if any((fc in url_lower if "/" in fc else (domain == fc or domain.endswith("." + fc))) for fc in self.FACT_CHECK_DOMAINS):
            return SourceAssessment(
                domain=domain,
                source_type="FACT_CHECK",
                credibility_weight=0.90,
                publisher=publisher or domain,
                is_known_fact_checker=True,
            )

        # 5. Reputable News Agencies
        if any(news in domain for news in self.REPUTABLE_NEWS_DOMAINS):
            return SourceAssessment(
                domain=domain,
                source_type="REPUTABLE_NEWS",
                credibility_weight=0.85,
                publisher=publisher or domain,
            )

        # 6. Fallback General / Other
        return SourceAssessment(
            domain=domain,
            source_type="OTHER",
            credibility_weight=0.60,
            publisher=publisher or domain,
        )


source_credibility_evaluator = SourceCredibilityEvaluator()
