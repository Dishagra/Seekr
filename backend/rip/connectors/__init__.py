from .github import GitHubConnector
from .openalex import OpenAlexConnector
from .dblp import DblpConnector
from .exa import ExaConnector
from .huggingface import HuggingFaceConnector
from .orcid import OrcidConnector
from .semanticscholar import SemanticScholarConnector
from .stackoverflow import StackOverflowConnector
from .web import WebConnector
from .wikidata import WikidataConnector

CONNECTORS = {
    "web": WebConnector,
    "wikidata": WikidataConnector,
    "dblp": DblpConnector,
    "exa": ExaConnector,
    "github": GitHubConnector,
    "huggingface": HuggingFaceConnector,
    "openalex": OpenAlexConnector,
    "orcid": OrcidConnector,
    "semanticscholar": SemanticScholarConnector,
    "stackoverflow": StackOverflowConnector,
}


def get_connector(source: str):
    try:
        return CONNECTORS[source]()
    except KeyError:
        raise ValueError(f"Unknown source '{source}'. Available: {sorted(CONNECTORS)}")
