"""Shared bottom-nav contract: each feature module contributes its own NavItems,
so the UI shell stays generic across security/finance/health/... modules."""
from dataclasses import dataclass


@dataclass(frozen=True)
class NavItem:
    slug: str
    label: str
    icon: str
    url: str
