AUDIO_MODEL_PATH = "bosonai/higgs-audio-v2-generation-3B-base"
AUDIO_TOKENIZER_PATH = "bosonai/higgs-audio-v2-tokenizer"
SAMPLE_RATE = 24000
MAX_FILE_SIZE_MB = 5
MAX_CONCURRENT_REQUESTS = 50

DEFAULT_SYSTEM_PROMPT = (
    "Generate audio following instruction.\n\n"
    "<|scene_desc_start|>\n"
    "Audio is recorded from a quiet room.\n"
    "<|scene_desc_end|>"
)

DEFAULT_STOP_STRINGS = ["<|end_of_text|>", "<|eot_id|>"]
TEMP_SAVE_DIR = "/tmp/higgs/"
TRANSCRIBE_MODEL_SIZE = "small"