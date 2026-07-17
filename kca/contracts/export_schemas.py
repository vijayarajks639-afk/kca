"""Export every contract model as JSON schema. Run via `make schemas`."""

import json
import sys
from pathlib import Path

from . import ALL_CONTRACT_MODELS

DEFAULT_OUT = Path(__file__).parent / "schemas"


def export_json_schemas(out_dir: Path) -> list[Path]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for model in ALL_CONTRACT_MODELS:
        path = out_dir / f"{model.__name__}.json"
        path.write_text(
            json.dumps(model.model_json_schema(), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        written.append(path)
    return written


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_OUT
    for p in export_json_schemas(target):
        print(p)
