from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class GatewayRepository:
    def __init__(self, store_root: Path) -> None:
        self.store_root = store_root
        self.projects_root = self.store_root / "projects"
        self.runs_root = self.store_root / "runs"
        self.projects_root.mkdir(parents=True, exist_ok=True)
        self.runs_root.mkdir(parents=True, exist_ok=True)

    def project_dir(self, project_id: str) -> Path:
        return self.projects_root / project_id

    def package_dir(self, project_id: str, package_id: str) -> Path:
        return self.project_dir(project_id) / "packages" / package_id

    def run_dir(self, run_id: str) -> Path:
        return self.runs_root / run_id

    def load_project(self, project_id: str) -> dict[str, Any]:
        return self.read_json(self.project_dir(project_id) / "project.json")

    def save_project(self, project_id: str, payload: dict[str, Any]) -> None:
        self.write_json(self.project_dir(project_id) / "project.json", payload)

    def load_package(self, project_id: str, package_id: str) -> dict[str, Any]:
        return self.read_json(self.package_dir(project_id, package_id) / "package.json")

    def save_package(self, project_id: str, package_id: str, payload: dict[str, Any]) -> None:
        self.write_json(self.package_dir(project_id, package_id) / "package.json", payload)

    def load_run(self, run_id: str) -> dict[str, Any]:
        return self.read_json(self.run_dir(run_id) / "meta" / "run.json")

    def save_run(self, run_id: str, payload: dict[str, Any]) -> None:
        self.write_json(self.run_dir(run_id) / "meta" / "run.json", payload)

    def load_status(self, run_id: str) -> dict[str, Any]:
        return self.read_json(self.run_dir(run_id) / "status.json")

    def save_status(self, run_id: str, payload: dict[str, Any]) -> None:
        self.write_json(self.run_dir(run_id) / "status.json", payload)

    def append_request_event(self, scope_dir: Path, payload: dict[str, Any]) -> Path:
        path = scope_dir / "request_events.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False) + "\n")
        return path

    def write_json(self, path: Path, payload: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = path.with_suffix(path.suffix + ".tmp")
        temp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        temp_path.replace(path)

    def read_json(self, path: Path) -> Any:
        return json.loads(path.read_text(encoding="utf-8"))
