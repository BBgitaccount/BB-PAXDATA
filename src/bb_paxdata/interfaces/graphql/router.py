# src/bb_paxdata/interfaces/graphql/router.py
from __future__ import annotations

from bb_paxdata.config.settings import get_settings
from bb_paxdata.interfaces.graphql.context import get_graphql_context
from bb_paxdata.interfaces.graphql.schema import schema
from strawberry.fastapi import GraphQLRouter

settings = get_settings()

# Prod ortamında introspection'ı kapat
graphql_router = GraphQLRouter(
    schema,
    context_getter=get_graphql_context,
    graphql_ide="graphiql" if settings.debug else None,
)
