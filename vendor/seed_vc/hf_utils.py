import os
from huggingface_hub import hf_hub_download
REVISIONS = {'Plachta/Seed-VC': '257283f9f41585055e8f858fba4fd044e5caed6e', 'Qwen/Qwen3-TTS-12Hz-0.6B-Base': '5d83992436eae1d760afd27aff78a71d676296fc', 'lj1995/VoiceConversionWebUI': 'e6d0c1a17da07c33557852f9dfa2bd44cc75737d', 'funasr/campplus': 'e4b6ede7ce16997aff4ae69fbca1f0175e2afede', 'nvidia/bigvgan_v2_44khz_128band_512x': '95a9d1dcb12906c03edd938d77b9333d6ded7dfb', 'openai/whisper-small': '973afd24965f72e36ca33b3055d56a652f456b4d'}


def load_custom_model_from_hf(repo_id, model_filename="pytorch_model.bin", config_filename=None):
    cache_dir = os.environ.get("SEED_MODEL_CACHE", os.environ.get("HF_HUB_CACHE", "./checkpoints"))
    os.makedirs(cache_dir, exist_ok=True)
    model_path = hf_hub_download(repo_id=repo_id, filename=model_filename, cache_dir=cache_dir, revision=REVISIONS.get(repo_id))
    if config_filename is None:
        return model_path
    config_path = hf_hub_download(repo_id=repo_id, filename=config_filename, cache_dir=cache_dir, revision=REVISIONS.get(repo_id))

    return model_path, config_path
