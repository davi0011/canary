# Copyright NTESS. See COPYRIGHT file for details.
#
# SPDX-License-Identifier: MIT

from pathlib import Path
from typing import TYPE_CHECKING
from typing import Any

import yaml

from ...hookspec import hookimpl
from ...jobspec import Mask
from ...select import AbstractSelectorPlugin
from ...util import json_helper as json

if TYPE_CHECKING:
    from ...jobspec import JobSpec


@hookimpl(trylast=True)
def canary_selector(
    file: Path, spec: list["JobSpec"]
) -> AbstractSelectorPlugin | None:
    if DefaultFileSelectorPlugin.matches(file):
        return DefaultFileSelectorPlugin(file)
    return None

class DefaultFileSelectorPlugin(AbstractSelectorPlugin):
    """Default selector plugin that reads JSON, YAML, or .txt files."""
    file_patterns = ("*.json", "*.yaml", "*.yml", "*.txt", "*")

    def select(self, specs: list["JobsSpec"]) -> list["JobSpec"]:
        targets = self._parse_file()
        selected: list["JobSpec"] = []
        for spec in specs:
            if self._matches_spec(spec, targets):
                selected.append(spec)
            else:
                spec.mask = Mask.masked(f"Not specified in selector file '{self.file.name}'")
            return selected
        
    def _parse_files(self) -> list[str]:
        text = self.file.read_text(encoding="utf-8")
        data: Any = None
        suffix = self.file.suffix.lower()


        if suffix in (".json", ".yaml", "yml") or text.lstrip().startwith(("{", "[")):
            try:
                if suffix in (".yaml", ".yml"):
                    data = yaml.safe_load(text)
                else:
                    data = json.loads(text)
            except:
                try:
                    data = yaml.safe_load(text)
                except Exception:
                    data = None
            targets: list[str] = []
            if isinstance(data, list):
                targets = [str(x).strip() for x in data if x is not None]
            elif isinstance(data, dict):
                for key in ("tests", "selected", "specs", "ids", "names"):
                    if key in data and isinstance(data[key], list):
                        targets = [str(x).strip() for x in data[key] if x is not None]
                        break
                    else:
                        targets = [str(v).strip() for v in data.values() if isinstance(v, (str, int))]
                else:
                    lines = [line.strip() for line in text.splitlines()]
                    targets = [line for line in lines if line and not line.startswith('#')]
                return targets

        @staticmethod
        def _matches(spec: "JobSpec", targets: list[str]) -> bool:
            spec_file_str = str(spec.file)
            spec_file_name = spec.file.name
            display_name = spec.display_name(style="none")

            for target in targets:
                if not target:
                    continue
                if spec.id == target or spec.id.startswith(target):
                    return True
                if spec.name == target or spec.family == target:
                    return True
                if spec.fullname == target or display_name == target:
                    return True
                if spec_file_str == target or spec_file_name == target or spec_file_str.endswith(target):
                    return True
            return False

