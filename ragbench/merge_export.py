"""Merge an adapter before evaluation and print the optional GGUF command."""
from pathlib import Path
import shlex


def merge(base_dir, adapter_dir, out_dir):
    from transformers import AutoModelForCausalLM, AutoTokenizer
    from peft import PeftModel

    base = AutoModelForCausalLM.from_pretrained(base_dir, local_files_only=True)
    model = PeftModel.from_pretrained(base, adapter_dir, local_files_only=True).merge_and_unload()
    model.save_pretrained(out_dir)
    AutoTokenizer.from_pretrained(base_dir, local_files_only=True).save_pretrained(out_dir)
    output = shlex.quote(str(out_dir))
    filename = shlex.quote(Path(out_dir).name + ".gguf")
    print(f"python <llama.cpp>/convert_hf_to_gguf.py {output} --outtype q8_0 --outfile {filename}")
