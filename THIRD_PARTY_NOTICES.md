# Third-party components

The optional Windows launcher downloads a private CPython 3.12.10 NuGet distribution from the CPython team's NuGet package and FFmpeg 8.1.2 from Gyan's Windows builds. Download URLs and pinned SHA-256 values are in `windows/runtime-pins.json`. These archives are downloaded during setup, and their license/source files are preserved in `.runtime/`. Python uses its PSF license; Gyan identifies these FFmpeg builds as GPLv3. The small project ZIP does not redistribute either runtime archive or the model weights.

This package contains required inference source from [Plachtaa/seed-vc](https://github.com/Plachtaa/seed-vc), commit `51383efd921027683c89e5348211d93ff12ac2a8`, under GPL-3.0. The upstream license is in `vendor/seed_vc/LICENSE`; original file notices and nested licenses are retained. The upstream README is also retained. Training programs, unrelated example recordings, and checkpoints are not distributed here.

Changes to the vendored source:

1. `inference.py` respects the deployment's Hugging Face cache and pins the Whisper and BigVGAN revisions used by this package.
2. `hf_utils.py` respects the configured cache and pins model downloads to `models.json` revisions. `SEED_MODEL_CACHE` is an optional development cache override.
3. `modules/length_regulator.py` imports the optional DAC quantizer only when vector quantization is enabled. The selected singing checkpoint has this option disabled, so unused DAC/training dependencies are unnecessary. The model computation is otherwise unchanged.

Dependencies and weights are downloaded from their upstream publishers at build/runtime:

| Component | Source | Upstream license |
|---|---|---|
| Seed-VC checkpoint | https://huggingface.co/Plachta/Seed-VC | GPL-3.0 |
| Qwen3-TTS library | https://github.com/QwenLM/Qwen3-TTS | Apache-2.0 |
| Qwen3-TTS 0.6B Base | https://huggingface.co/Qwen/Qwen3-TTS-12Hz-0.6B-Base | Apache-2.0 |
| Demucs library / HTDemucs weights | https://github.com/adefossez/demucs | MIT |
| RMVPE weights | https://huggingface.co/lj1995/VoiceConversionWebUI | MIT (repository metadata) |
| CAMPPlus weights | https://huggingface.co/funasr/campplus | Apache-2.0 |
| BigVGAN weights | https://huggingface.co/nvidia/bigvgan_v2_44khz_128band_512x | MIT |
| Whisper small weights | https://huggingface.co/openai/whisper-small | Apache-2.0 |
| Gradio | https://github.com/gradio-app/gradio | Apache-2.0 |
| PyTorch / torchaudio | https://github.com/pytorch/pytorch | BSD-style; see each distribution |

Installed packages include their own license files. FFmpeg, SoX, and system libraries come from Debian packages with their respective licenses; they are not relicensed by this project. Audio references and user uploads are separate from the code license, as described in the main README.

Pinned model revision identifiers and model-card license metadata are in `models.json`. No person-specific trained checkpoint is claimed or included.
