"""Fast, offline installation checks used by the Windows launcher."""
import argparse
import importlib.metadata
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["ui", "singing", "speech", "gpu", "tools"])
    args = parser.parse_args()
    if sys.version_info[:2] != (3, 12):
        raise RuntimeError("This app needs its private Python 3.12 runtime. Run Repair setup.")
    report = {"mode": args.mode, "python": sys.version.split()[0]}
    if args.mode == "ui":
        import gradio
        assert gradio.__version__ == "6.31.0", "Wrong interface version. Run Repair setup."
        sys.path.insert(0, str(ROOT))
        import app
        app.build_app()
        report["gradio"] = gradio.__version__
    elif args.mode in ["singing", "speech", "gpu"]:
        import torch
        import torchaudio
        assert torch.__version__.split("+")[0] == "2.7.1", "Wrong GPU runtime version. Run Repair setup."
        assert torchaudio.__version__.split("+")[0] == "2.7.1", "Wrong audio runtime version. Run Repair setup."
        report["torch"] = torch.__version__
        if args.mode == "gpu":
            if not torch.cuda.is_available():
                raise RuntimeError("The NVIDIA driver is not ready for this app. Update the driver, restart Windows, and try again.")
            # Execute a real operation, rather than just detecting the card.
            assert torch.arange(16, device="cuda").sum().item() == 120
            report.update(gpu=torch.cuda.get_device_name(), vram_gb=round(torch.cuda.get_device_properties(0).total_memory / 1024**3, 1))
        elif args.mode == "singing":
            from demucs.api import Separator
            import soundfile
            import scipy
            import transformers
            sys.path.insert(0, str(ROOT / "vendor/seed_vc"))
            import inference
            report["transformers"] = transformers.__version__
        else:
            from qwen_tts import Qwen3TTSModel
            import transformers
            report["transformers"] = transformers.__version__
    else:
        for name in ["FFMPEG", "FFPROBE"]:
            path = Path(os.environ[name])
            result = subprocess.run([str(path), "-version"], capture_output=True, text=True, timeout=20)
            if result.returncode:
                raise RuntimeError(f"{name} did not start. Run Repair setup.")
            report[name] = result.stdout.splitlines()[0]
    print("@@CHECK " + json.dumps(report), flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print("Setup check failed: " + str(error), file=sys.stderr, flush=True)
        sys.exit(1)
