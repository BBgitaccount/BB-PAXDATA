from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bb_paxdata.infrastructure.db.models import CountryPairSentiment
from bb_paxdata.interfaces.api.dependencies import get_db
from bb_paxdata.interfaces.api.schemas import (
    CountryConnection,
    CountryNode,
    WorldMapResponse,
)

router = APIRouter(
    prefix="/worldmap",
    tags=["WorldMap"],
)

# Country coordinates mapping (ISO 3166-1 alpha-3 to lat/lon)
COUNTRY_COORDINATES = {
    "USA": (38.0, -97.0),
    "TUR": (39.0, 35.0),
    "RUS": (61.0, 105.0),
    "CHN": (35.0, 105.0),
    "GBR": (55.0, -3.0),
    "FRA": (46.0, 2.0),
    "DEU": (51.0, 10.0),
    "ITA": (42.0, 12.0),
    "ESP": (40.0, -4.0),
    "POL": (52.0, 20.0),
    "UKR": (49.0, 32.0),
    "JPN": (36.0, 138.0),
    "KOR": (37.0, 128.0),
    "IND": (21.0, 78.0),
    "PAK": (30.0, 69.0),
    "IRN": (32.0, 53.0),
    "SAU": (24.0, 45.0),
    "EGY": (26.0, 30.0),
    "BRA": (-14.0, -51.0),
    "ARG": (-34.0, -64.0),
    "MEX": (23.0, -102.0),
    "CAN": (56.0, -106.0),
    "AUS": (-25.0, 134.0),
    "IDN": (-0.8, 113.0),
    "NGA": (10.0, 8.0),
    "ZAF": (-30.0, 25.0),
    "COL": (4.0, -72.0),
    "VEN": (7.0, -66.0),
    "CHL": (-30.0, -71.0),
    "PER": (-10.0, -76.0),
    "GRC": (39.0, 22.0),
    "PRT": (39.0, -8.0),
    "NLD": (52.0, 5.0),
    "BEL": (50.0, 4.0),
    "AUT": (47.0, 15.0),
    "CHE": (47.0, 8.0),
    "SWE": (60.0, 18.0),
    "NOR": (62.0, 10.0),
    "DNK": (56.0, 10.0),
    "FIN": (62.0, 25.0),
    "CZE": (49.0, 15.0),
    "HUN": (47.0, 20.0),
    "ROU": (46.0, 25.0),
    "BGR": (43.0, 25.0),
    "SRB": (44.0, 21.0),
    "HRV": (45.0, 16.0),
    "BIH": (44.0, 18.0),
    "SVN": (46.0, 15.0),
    "SVK": (48.0, 19.0),
    "EST": (59.0, 26.0),
    "LVA": (57.0, 25.0),
    "LTU": (56.0, 24.0),
    "BLR": (53.0, 28.0),
    "MDA": (47.0, 29.0),
    "GEO": (42.0, 43.0),
    "ARM": (40.0, 45.0),
    "AZE": (40.0, 47.0),
    "KAZ": (48.0, 68.0),
    "UZB": (41.0, 64.0),
    "TKM": (39.0, 59.0),
    "KGZ": (41.0, 75.0),
    "TJK": (39.0, 71.0),
    "AFG": (33.0, 65.0),
    "IRQ": (33.0, 44.0),
    "SYR": (35.0, 38.0),
    "JOR": (31.0, 36.0),
    "LBN": (34.0, 36.0),
    "ISR": (31.0, 35.0),
    "PSE": (32.0, 35.0),
    "KWT": (29.0, 47.0),
    "BHR": (26.0, 50.0),
    "QAT": (25.0, 51.0),
    "ARE": (24.0, 54.0),
    "OMN": (21.0, 57.0),
    "YEM": (15.0, 48.0),
    "MAR": (32.0, -6.0),
    "DZA": (28.0, 2.0),
    "TUN": (34.0, 9.0),
    "LBY": (25.0, 17.0),
    "SDN": (13.0, 30.0),
    "ETH": (9.0, 39.0),
    "KEN": (1.0, 38.0),
    "TZA": (-6.0, 35.0),
    "UGA": (1.0, 32.0),
    "RWA": (-2.0, 30.0),
    "COD": (-4.0, 23.0),
    "ZWE": (-20.0, 30.0),
    "ZMB": (-14.0, 30.0),
    "MWI": (-14.0, 34.0),
    "MOZ": (-18.0, 35.0),
    "AGO": (-12.0, 18.0),
    "NAM": (-22.0, 17.0),
    "BWA": (-22.0, 24.0),
    "LSO": (-29.0, 28.0),
    "SWZ": (-26.0, 31.0),
    "MDG": (-20.0, 47.0),
    "MUS": (-20.0, 57.0),
    "COM": (-12.0, 44.0),
    "SYC": (-4.0, 55.0),
    "DJI": (11.0, 43.0),
    "SOM": (5.0, 49.0),
    "ERI": (15.0, 39.0),
    "SSD": (7.0, 30.0),
    "CMR": (6.0, 12.0),
    "BEN": (9.0, 2.0),
    "TGO": (8.0, 1.0),
    "GHA": (8.0, -2.0),
    "CIV": (8.0, -5.0),
    "GIN": (10.0, -10.0),
    "SEN": (14.0, -14.0),
    "MLI": (17.0, -4.0),
    "BFA": (13.0, -2.0),
    "NER": (16.0, 8.0),
    "TCD": (15.0, 19.0),
    "CAF": (7.0, 21.0),
    "COG": (-1.0, 15.0),
    "GAB": (-1.0, 12.0),
    "GNQ": (1.0, 10.0),
    "STP": (0.0, 7.0),
    "GMB": (13.0, -16.0),
    "GNB": (12.0, -15.0),
    "SLE": (8.0, -12.0),
    "LBR": (6.0, -10.0),
    "MRT": (21.0, -10.0),
    "CUB": (21.0, -80.0),
    "HTI": (19.0, -72.0),
    "DOM": (19.0, -71.0),
    "JAM": (18.0, -77.0),
    "TTO": (11.0, -61.0),
    "BRB": (13.0, -59.0),
    "GRD": (12.0, -62.0),
    "LCA": (14.0, -61.0),
    "VCT": (13.0, -61.0),
    "ATG": (17.0, -62.0),
    "DMA": (15.0, -61.0),
    "KNA": (17.0, -62.0),
    "BLZ": (17.0, -88.0),
    "GTM": (16.0, -90.0),
    "SLV": (14.0, -89.0),
    "HND": (15.0, -86.0),
    "NIC": (13.0, -85.0),
    "CRI": (10.0, -84.0),
    "PAN": (9.0, -80.0),
    "ECU": (-2.0, -78.0),
    "BOL": (-17.0, -65.0),
    "PRY": (-23.0, -58.0),
    "URY": (-33.0, -56.0),
    "GUY": (5.0, -59.0),
    "SUR": (4.0, -56.0),
    "FLK": (-52.0, -59.0),
    "MYS": (4.0, 109.0),
    "SGP": (1.0, 104.0),
    "THA": (15.0, 101.0),
    "VNM": (16.0, 106.0),
    "LAO": (18.0, 105.0),
    "KHM": (13.0, 105.0),
    "MMR": (22.0, 98.0),
    "BGD": (24.0, 90.0),
    "LKA": (7.0, 81.0),
    "NPL": (28.0, 84.0),
    "BTN": (27.0, 90.0),
    "MDV": (3.0, 73.0),
    "PHL": (13.0, 122.0),
    "TLS": (-9.0, 126.0),
    "PNG": (-6.0, 147.0),
    "NZL": (-41.0, 174.0),
    "FJI": (-18.0, 178.0),
    "SLB": (-8.0, 159.0),
    "VUT": (-16.0, 167.0),
    "NCL": (-21.0, 165.0),
    "PYF": (-17.0, -149.0),
    "ASM": (-14.0, -170.0),
    "GUM": (13.0, 145.0),
    "MNP": (15.0, 145.0),
    "PRI": (18.0, -66.0),
    "VIR": (18.0, -65.0),
}


@router.get("/data", response_model=WorldMapResponse)
async def get_world_map_data(
    db: AsyncSession = Depends(get_db),
    min_interactions: int = Query(
        default=1, ge=1, description="Minimum interaction count to include a connection"
    ),
):
    """Get country relationship data for world map visualization.

    Returns nodes (countries with coordinates) and connections (relationships between countries).
    """
    # Get all country pair sentiment data
    stmt = select(CountryPairSentiment).where(
        CountryPairSentiment.interaction_count >= min_interactions
    )
    result = await db.execute(stmt)
    pairs = result.scalars().all()

    # Build set of all unique countries
    countries = set()
    for pair in pairs:
        countries.add(pair.from_country)
        countries.add(pair.to_country)

    # Create country nodes with coordinates
    nodes = []
    for country in countries:
        coords = COUNTRY_COORDINATES.get(country)
        if not coords:
            continue

        # Calculate aggregate stats for this country
        from_mentions = sum(
            p.total_mentions for p in pairs if p.from_country == country
        )
        to_mentions = sum(p.total_mentions for p in pairs if p.to_country == country)
        total_mentions = from_mentions + to_mentions

        # Calculate average sentiment
        sentiments = []
        for p in pairs:
            if p.from_country == country and p.avg_sentiment:
                sentiments.append(p.avg_sentiment)
            if p.to_country == country and p.avg_sentiment:
                sentiments.append(p.avg_sentiment)

        avg_sentiment = sum(sentiments) / len(sentiments) if sentiments else 0.0

        nodes.append(
            CountryNode(
                country_code=country,
                country_name=country,  # Could be enhanced with a lookup table
                latitude=coords[0],
                longitude=coords[1],
                total_mentions=total_mentions,
                avg_sentiment=avg_sentiment,
            )
        )

    # Create connections between countries
    connections = []
    for pair in pairs:
        from_coords = COUNTRY_COORDINATES.get(pair.from_country)
        to_coords = COUNTRY_COORDINATES.get(pair.to_country)

        if not from_coords or not to_coords:
            continue

        connections.append(
            CountryConnection(
                from_country=pair.from_country,
                to_country=pair.to_country,
                from_lat=from_coords[0],
                from_lon=from_coords[1],
                to_lat=to_coords[0],
                to_lon=to_coords[1],
                avg_sentiment=pair.avg_sentiment or 0.0,
                interaction_count=pair.interaction_count,
                relationship_type=(
                    pair.relationship_type.value
                    if pair.relationship_type
                    else "NEUTRAL"
                ),
                affinity_score=pair.affinity_score or 0.0,
            )
        )

    return WorldMapResponse(
        nodes=nodes,
        connections=connections,
    )
