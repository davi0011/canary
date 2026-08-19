import pytest
from pathlib import Path
from unittest.mock import MagicMock

from _canary.jobspec import JobSpec
from _canary.select import AbstractSelectorPlugin, FileSelectorRule, Selector
from _canary.workspace import Workspace

# --- Mocks and Helpers ---

class MockSelectorPlugin(AbstractSelectorPlugin):
    """A simple selector plugin for testing purposes."""
    file_patterns = ("*.testlist",)

    def select(self, specs: list[JobSpec]) -> list[JobSpec]:
        # Mock logic: select specs whose IDs are mentioned in the file
        with open(self.file, "r") as f:
            allowed_ids = {line.strip() for line in f if line.strip()}
        return [s for s in specs if s.id in allowed_ids]

@pytest.fixture
def mock_specs():
    """Provides a list of dummy JobSpec objects."""
    return [
        MagicMock(spec=JobSpec, id="test_1"),
        MagicMock(spec=JobSpec, id="test_2"),
        MagicMock(spec=JobSpec, id="test_3"),
    ]

@pytest.fixture
def selector_file(tmp_path, mock_specs):
    """Creates a temporary selector file."""
    f = tmp_path / "tests.testlist"
    f.write_text("test_1\ntest_3")
    return f

# --- Unit Tests for AbstractSelectorPlugin ---

def test_selector_plugin_matches():
    assert MockSelectorPlugin.matches(Path("my_tests.testlist")) is True
    assert MockSelectorPlugin.matches(Path("my_tests.txt")) is False

def test_selector_plugin_select(selector_file, mock_specs):
    plugin = MockSelectorPlugin(selector_file)
    selected = plugin.select(mock_specs)
    selected_ids = {s.id for s in selected}
    assert selected_ids == {"test_1", "test_3"}

# --- Unit Tests for FileSelectorRule ---

def test_file_selector_rule_filtering(mock_specs):
    ## Setup mock specs with IDs
    mock_specs[0].id = "test_1"
    mock_specs[1].id = "test_2"
    mock_specs[2].id = "test_3"

    # Manually populate selected_ids to test the __call__ logic
    rule = FileSelectorRule(selector_file="dummy.txt")
    rule.selected_ids = {"test_1", "test_3"}

    assert rule(mock_specs[0])
    assert not rule(mock_specs[1])
    assert rule(mock_specs[2])

# --- Integration Tests for Selector ---

def test_selector_run_with_file_rule(selector_file, mock_specs, tmp_path):
    for spec in mock_specs:
        spec.mask = None
        spec.dependencies = []

    selector = Selector(mock_specs, tmp_path)
    selector.add_rule(FileSelectorRule(selector_file))

    # Mock the rule's internal state
    for rule in selector.rules:
        if isinstance(rule, FileSelectorRule):
            rule.selected_ids = {"test_1", "test_3"}

    results = selector.run()
    assert len(results) == 2  # Should select test_1 and test_3

# --- Workspace Integration Tests ---

@pytest.fixture
def chdir_tmp(tmp_path, monkeypatch):
    """Fixture that changes working directory to tmp_path for the test."""
    monkeypatch.chdir(tmp_path)
    return tmp_path

# Then the test can remain as is:
def test_workspace_filter_specs_with_selector_file(chdir_tmp, mock_specs, selector_file):
    root = chdir_tmp / "proj"
    root.mkdir()
    ws = Workspace.create(root)

    # Mock the internal selector
    with pytest.MonkeyPatch.context() as mp:
        def mock_init(*args, **kwargs):
            instance = MagicMock(spec=FileSelectorRule)
            instance.selected_ids = {"test_1"}
            # Fix: RuleOutcome should be returned, not a mock with outcome attribute
            from _canary.rules import RuleOutcome
            instance.__call__ = lambda spec: RuleOutcome(spec.id in instance.selected_ids)
            return instance

        # Fixed: Use the correct module path _canary.select instead of canary.select
        mp.setattr("_canary.select.FileSelectorRule", mock_init)

        specs = ws.filter_specs(
            mock_specs,
            selector_file=selector_file
        )
        assert len(specs) > 0