import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any
from schemas import RunRecord, StageEntry

class EntityManager:
    def __init__(self, storage_root: Path):
        self.storage_root = Path(storage_root)
        
    def ingest_run(self, evidence_dir: Path, run_id: str, project_id: str, subject_id: str = "elon_musk"):
        evidence_dir = Path(evidence_dir)
        # 确定产物存放路径
        output_dir = self.storage_root / subject_id
        output_dir.mkdir(parents=True, exist_ok=True)

        # 1. 初始化 Run 级信息 (ID / 时间戳 / 运行状态)
        record = RunRecord(
            run_id=run_id,
            project_id=project_id,
            subject_id=subject_id,
            trace_id=f"trace_{run_id}",  # 模拟 trace_id
            status="completed",           # 运行状态
            started_at=self._extract_time(evidence_dir), # 时间戳
        )

        log_file = evidence_dir / "91_http_codes.txt"
        record.log_summary = log_file.read_text(encoding="utf-8") if log_file.exists() else ""

        for body_file in sorted(evidence_dir.glob("*.body.json")):
            stage = StageEntry(
                stage_key=body_file.stem.replace(".body", ""),
                status="completed",
                output_ref=str(body_file.absolute()),
                error_message=None # 如果 200 则为 None
            )
            stage.metadata = {"request_id": f"req_{stage.stage_key}"}
            record.stages.append(stage)

        manifest_path = output_dir / "run_manifest.json"
        manifest_path.write_text(record.model_dump_json(indent=2), encoding="utf-8")
        
        print(f"✅ 极简 Manifest 已生成: {manifest_path}")
        return manifest_path

    def _extract_time(self, path: Path):
        parts = path.name.split('_')
        return f"{parts[-2]} {parts[-1]}" if len(parts) >= 3 else str(datetime.now())