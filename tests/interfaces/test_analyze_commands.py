# tests/interfaces/test_analyze_commands.py
from unittest.mock import AsyncMock, MagicMock, patch

from bb_paxdata.application.use_cases.aggregate_bilateral_sentiment import (
    AggregateBilateralSentimentOutput,
)
from bb_paxdata.application.use_cases.build_panel_network import BuildPanelNetworkOutput
from bb_paxdata.interfaces.cli.commands.analyze import app
from typer.testing import CliRunner

runner = CliRunner()


def test_country_refs_command_success() -> None:
    mock_output = AggregateBilateralSentimentOutput(
        panel_id="p001",
        created_count=3,
        updated_count=1,
        total_pairs=4,
    )

    with patch(
        "bb_paxdata.interfaces.cli.commands.analyze.get_session"
    ) as mock_session, patch(
        "bb_paxdata.interfaces.cli.commands.analyze.make_aggregate_bilateral_use_case"
    ) as mock_factory, patch(
        "bb_paxdata.infrastructure.db.repositories.country_repository.BilateralSentimentRepository"
    ) as mock_repo_class:
        mock_use_case = AsyncMock()
        mock_use_case.execute.return_value = mock_output
        mock_factory.return_value = mock_use_case
        mock_session.return_value.__aenter__ = AsyncMock(return_value=MagicMock())
        mock_session.return_value.__aexit__ = AsyncMock(return_value=False)

        mock_repo = AsyncMock()
        mock_repo_class.return_value = mock_repo

        result = runner.invoke(app, ["country-refs", "--panel-id", "p001"])

    assert result.exit_code == 0
    assert "Tamamlandı" in result.output
    assert "3" in result.output  # created_count


def test_country_refs_command_exits_1_on_full_failure() -> None:
    mock_output = AggregateBilateralSentimentOutput(
        panel_id="p001",
        created_count=0,
        updated_count=0,
        total_pairs=0,
        errors=("DB bağlantısı kesildi",),
    )

    with patch(
        "bb_paxdata.interfaces.cli.commands.analyze.get_session"
    ) as mock_session, patch(
        "bb_paxdata.interfaces.cli.commands.analyze.make_aggregate_bilateral_use_case"
    ) as mock_factory:
        mock_use_case = AsyncMock()
        mock_use_case.execute.return_value = mock_output
        mock_factory.return_value = mock_use_case
        mock_session.return_value.__aenter__ = AsyncMock(return_value=MagicMock())
        mock_session.return_value.__aexit__ = AsyncMock(return_value=False)

        result = runner.invoke(app, ["country-refs", "--panel-id", "p001"])

    assert result.exit_code == 1


def test_network_command_shows_centrality() -> None:
    mock_output = BuildPanelNetworkOutput(
        panel_id="p001",
        edges_created=5,
        node_count=4,
        centrality={"TR": 0.8, "US": 0.6, "DE": 0.3},
    )

    with patch(
        "bb_paxdata.interfaces.cli.commands.analyze.get_session"
    ) as mock_session, patch(
        "bb_paxdata.interfaces.cli.commands.analyze.make_build_network_use_case"
    ) as mock_factory:
        mock_use_case = AsyncMock()
        mock_use_case.execute.return_value = mock_output
        mock_factory.return_value = mock_use_case
        mock_session.return_value.__aenter__ = AsyncMock(return_value=MagicMock())
        mock_session.return_value.__aexit__ = AsyncMock(return_value=False)

        result = runner.invoke(app, ["network", "--panel-id", "p001", "--centrality"])

    import re

    cleaned_output = re.sub(r"\x1b\[[0-9;]*[a-zA-Z]", "", result.output)
    assert result.exit_code == 0
    assert "4 düğüm" in cleaned_output
    assert "TR" in cleaned_output
