"""Cross-domain discovery (WP-23) — thin metadata/entity pointers across domains,
no content; Haiku intent classification via the gateway; authorisation enforced
at each domain boundary.
"""

from kca.platform.discovery.domains import DomainDescriptor, descriptor_from_dip
from kca.platform.discovery.index import DiscoveryIndex
from kca.platform.discovery.intent import IntentClassification, IntentClassifier

__all__ = [
    "DiscoveryIndex",
    "DomainDescriptor",
    "IntentClassification",
    "IntentClassifier",
    "descriptor_from_dip",
]
