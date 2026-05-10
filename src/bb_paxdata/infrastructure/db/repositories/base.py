"""Abstract repository interface."""

from abc import ABC, abstractmethod
from typing import Generic, TypeVar

T = TypeVar("T")


class AbstractRepository(ABC, Generic[T]):
    """Generic persistence port; implementations map ORM rows to domain models."""

    @abstractmethod
    def get(self, entity_id: str) -> T | None:
        """Return a single domain entity by primary identifier."""

    @abstractmethod
    def add(self, entity: T) -> None:
        """Stage a new domain entity for insert on flush/commit."""

    def add_many(self, entities: list[T]) -> None:
        """Stage multiple new entities (default: repeated ``add``)."""
        for entity in entities:
            self.add(entity)

    @abstractmethod
    def remove(self, entity: T) -> None:
        """Delete the given domain entity (resolved via ORM in concrete repos)."""
