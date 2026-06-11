# src/bb_paxdata/interfaces/graphql/router.py
from __future__ import annotations

from typing import Any

from bb_paxdata.config.settings import Settings, get_settings
from bb_paxdata.interfaces.graphql.context import get_graphql_context
from bb_paxdata.interfaces.graphql.schema import schema
from strawberry.fastapi import GraphQLRouter


def create_graphql_router(
    settings: Settings | None = None,
) -> GraphQLRouter[dict[str, Any], Any]:
    """
    Factory function to create GraphQL router with dependency injection.
    """
    if settings is None:
        settings = get_settings()

    # Prod ortamında introspection'ı kapat
    return GraphQLRouter(
        schema,
        context_getter=get_graphql_context,
        graphql_ide="graphiql" if settings.debug else None,
    )


# Default router for backward compatibility (lazy initialization)
graphql_router: GraphQLRouter[dict[str, Any], Any] | None = None


def get_graphql_router() -> GraphQLRouter[dict[str, Any], Any]:
    """Get or create the default GraphQL router."""
    global graphql_router
    if graphql_router is None:
        graphql_router = create_graphql_router()
    return graphql_router
