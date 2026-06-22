import shutil
import tempfile
from pathlib import Path

import pytest

from bb_paxdata.application.domain.services.cross_anomaly_service import (
    CrossAnomalyService,
)
from bb_paxdata.application.domain.services.rule_registry import RuleRegistry


@pytest.fixture
def temp_rules_dir():
    temp_dir = tempfile.mkdtemp()
    yield Path(temp_dir)
    shutil.rmtree(temp_dir)


@pytest.mark.asyncio
class TestRuleRegistryAndService:
    async def test_registry_loads_valid_rules(self, temp_rules_dir):
        rule_code = """
from bb_paxdata.application.domain.models.rule_anomaly import RuleAnomaly
from bb_paxdata.application.domain.enums import AnomalySeverity

class MockRule:
    @property
    def rule_id(self): return "mock_rule_1"
    @property
    def rule_name(self): return "Mock Rule"
    def evaluate(self, ctx): return []
    def get_metadata(self): return {}
"""
        with open(temp_rules_dir / "mock_rule.py", "w", encoding="utf-8") as f:
            f.write(rule_code)

        registry = RuleRegistry(temp_rules_dir)
        await registry.reload()

        assert len(registry.rules) == 1
        assert registry.rules[0].rule_id == "mock_rule_1"
        assert len(registry.failed_rules) == 0

    async def test_fault_tolerance_on_invalid_rule(self, temp_rules_dir):
        # File with SyntaxError
        bad_code = "class BrokenRule: syntax error here"
        with open(temp_rules_dir / "broken_rule.py", "w", encoding="utf-8") as f:
            f.write(bad_code)

        registry = RuleRegistry(temp_rules_dir)
        await registry.reload()

        # Registry must not crash; broken_rule should be recorded as failed
        assert len(registry.rules) == 0
        assert len(registry.failed_rules) == 1
        assert registry.failed_rules[0][0] == "broken_rule"

    async def test_hot_reload_on_service(self, temp_rules_dir):
        registry = RuleRegistry(temp_rules_dir)
        service = CrossAnomalyService(registry=registry)
        await service.initialize()

        assert len(registry.rules) == 0

        # Dynamically add a rule
        rule_code = """
class DynamicRule:
    @property
    def rule_id(self): return "dynamic_1"
    @property
    def rule_name(self): return "Dynamic Rule"
    def evaluate(self, ctx): return []
    def get_metadata(self): return {}
"""
        with open(temp_rules_dir / "dynamic_rule.py", "w", encoding="utf-8") as f:
            f.write(rule_code)

        report = await service.reload_rules()
        assert report.total_rules == 1
        assert registry.rules[0].rule_id == "dynamic_1"
