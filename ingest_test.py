import os
from pathlib import Path
from storage import EntityManager

# 获取当前脚本所在目录 (AnalyzingAnyone/)
BASE_DIR = Path(__file__).resolve().parent

# 1. 使用相对路径定位证据目录和输出目录
# 假设你的证据文件夹就在项目根目录下
EVI_DIR = BASE_DIR / "integration_evidence_20260421_185337"
OUTPUT_ROOT = BASE_DIR / "output"

# 2. 初始化管理器
db = EntityManager(OUTPUT_ROOT)

try:
    # 3. 执行入库
    record = db.ingest_run(
        evidence_dir=EVI_DIR, 
        run_id="run_6a63590f", 
        project_id="proj_88af46f3"
    )
    print(f"处理完成！Manifest 已存至: {record.output_dir}/run_manifest.json")
except Exception as e:
    print(f"运行失败: {e}")