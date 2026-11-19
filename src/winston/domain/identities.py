"""Typed identity wrappers for domain entities."""

from datetime import date
from typing import NewType

# Stable identifiers - these are semantic, not database PKs
IndexId = NewType("IndexId", str)
ExecutionId = NewType("ExecutionId", str)
RevisionId = NewType("RevisionId", str)
ArtifactId = NewType("ArtifactId", str)
ManifestId = NewType("ManifestId", str)
IssueId = NewType("IssueId", str)
ObligationId = NewType("ObligationId", str)
RepositoryId = NewType("RepositoryId", str)
ComponentId = NewType("ComponentId", str)

# Business date is a semantic date, not a timestamp
BusinessDate = NewType("BusinessDate", date)
