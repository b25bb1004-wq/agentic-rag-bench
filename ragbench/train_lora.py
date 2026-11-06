"""Offline LoRA training with assistant-only supervision."""
import argparse
import contextlib
import json
import math
from pathlib import Path

from ragbench.sft import read_jsonl


def encode_conversation(tokenizer, messages, max_len=1536):
    """Expand assistant turns using the same generation prompt as inference."""
    examples = []
    for i, message in enumerate(messages):
        if message["role"] != "assistant":
            continue
        prompt_ids = tokenizer.apply_chat_template(
            messages[:i], tokenize=True, add_generation_prompt=True,
            enable_thinking=False, return_dict=False,
        )
        target_ids = tokenizer(
            message["content"] + "<|im_end|>", add_special_tokens=False,
        ).input_ids
        ids = prompt_ids + target_ids
        labels = [-100] * len(prompt_ids) + target_ids
        # Validate complete examples before training; never silently cut targets.
        assert len(ids) <= max_len, f"example would be truncated at --max_len={max_len}"
        if not any(label != -100 for label in labels[1:]):
            raise ValueError("no assistant tokens in example")
        examples.append({"input_ids": ids, "attention_mask": [1] * len(ids),
                         "labels": labels})
    if not examples:
        raise ValueError("conversation has no assistant response")
    return examples


def validate_lengths(tokenizer, records, max_len, *, examples=None):
    """Check expanded examples, or full records for legacy callers."""
    if examples is None:
        lengths = [len(tokenizer.apply_chat_template(row["messages"], tokenize=True,
                                                   add_generation_prompt=False)) for row in records]
        unit = "records"
    else:
        lengths = [len(example["input_ids"]) for example in examples]
        unit = "examples"
    truncated = sum(length > max_len for length in lengths)
    assert not truncated, f"{truncated} {unit} would be truncated at --max_len={max_len}"
    if not lengths:
        raise ValueError("empty training data")
    return lengths


def target_loss(model, tensors):
    """Project only hidden states that predict supervised target tokens."""
    from torch.nn.functional import cross_entropy

    targets = tensors["labels"][:, 1:]
    selected = targets != -100
    if not selected.any():
        raise ValueError("batch has no supervised target tokens after shifting labels")
    inner = model.get_base_model() if hasattr(model, "get_base_model") else model
    hidden = inner.model(
        input_ids=tensors["input_ids"], attention_mask=tensors["attention_mask"],
    ).last_hidden_state
    # .to() is a no-op on one device; with a model split across GPUs the last layer sits elsewhere
    logits = inner.lm_head(hidden[:, :-1][selected.to(hidden.device)]).float()
    return cross_entropy(logits, targets.to(logits.device)[selected.to(logits.device)])


def lora_params_to_fp32(model):
    """fp16amp: frozen base stays fp16, trainable LoRA weights become fp32 master weights."""
    import torch
    for param in model.parameters():
        if param.requires_grad:
            param.data = param.data.to(torch.float32)


def train(args):
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer, Qwen3Config, Qwen3ForCausalLM, set_seed
    from peft import LoraConfig, get_peft_model

    set_seed(args.seed)
    torch.use_deterministic_algorithms(True, warn_only=True)
    if min(args.bs, args.grad_accum, args.max_len, args.rank) <= 0 or args.epochs <= 0:
        raise ValueError("batch, accumulation, length, rank and epochs must be positive")
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    tokenizer = AutoTokenizer.from_pretrained(args.base, local_files_only=True)
    records = read_jsonl(args.data)
    examples = [example for row in records
                for example in encode_conversation(tokenizer, row["messages"], args.max_len)]
    lengths = validate_lengths(tokenizer, records, args.max_len, examples=examples)
    device = "cpu" if args.dry_run else ("cuda" if torch.cuda.is_available() else "mps" if torch.backends.mps.is_available() else "cpu")
    # auto: bf16 as on the Mac. fp16amp: for GPUs without bf16 (Kaggle T4/P100), fp16 base + fp32 LoRA + loss scaling.
    precision = getattr(args, "precision", "auto")
    split = getattr(args, "split_gpus", False)
    if precision == "fp16amp" and device != "cuda":
        raise ValueError("fp16amp needs a CUDA device")
    if split and precision != "fp16amp":
        raise ValueError("split_gpus is only supported with fp16amp")
    dtype = torch.float32 if device == "cpu" else torch.float16 if precision == "fp16amp" else torch.bfloat16
    if args.dry_run:
        config = Qwen3Config(vocab_size=len(tokenizer), hidden_size=64, intermediate_size=128, num_hidden_layers=2, num_attention_heads=4, num_key_value_heads=2, head_dim=16, max_position_embeddings=args.max_len)
        model = Qwen3ForCausalLM(config)
    else:
        # split_gpus: layer-split one model over all visible GPUs (Qwen3-8B fp16 is 16 GB, more than one T4)
        model = AutoModelForCausalLM.from_pretrained(args.base, local_files_only=True, torch_dtype=dtype,
                                                     **({"device_map": "auto"} if split else {}))
    model = get_peft_model(model, LoraConfig(r=args.rank, lora_alpha=args.alpha, target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"], task_type="CAUSAL_LM"))
    if not split:
        model.to(device=device, dtype=dtype)
    if precision == "fp16amp":
        lora_params_to_fp32(model)
        if split:
            device = "cuda:0"  # inputs enter at the embedding on the first GPU
    scaler = torch.amp.GradScaler("cuda") if precision == "fp16amp" else None
    autocast = (lambda: torch.autocast("cuda", dtype=torch.float16)) if precision == "fp16amp" else contextlib.nullcontext
    model.train()
    model.config.use_cache = False
    # keep only layer inputs for backprop: a 2048-token example needed 16.7 GB on MPS without this (OOM on a 16 GB Mac)
    model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={"use_reentrant": False})
    model.enable_input_require_grads()
    pad = tokenizer.pad_token_id if tokenizer.pad_token_id is not None else tokenizer.eos_token_id
    if pad is None:
        raise ValueError("tokenizer needs a pad or EOS token")
    optimizer = torch.optim.AdamW((p for p in model.parameters() if p.requires_grad), lr=args.lr)
    generator = torch.Generator().manual_seed(args.seed)
    microbatches = 2 * args.grad_accum if args.dry_run else math.ceil(args.epochs * math.ceil(len(examples) / args.bs))
    updates = math.ceil(microbatches / args.grad_accum)
    order, cursor = [], 0
    consumed = 0
    with (out / "train_log.jsonl").open("w") as log:
        for step in range(1, updates + 1):
            optimizer.zero_grad()
            total_loss = 0.0
            accumulation = min(args.grad_accum, microbatches - consumed)
            for _ in range(accumulation):
                if cursor >= len(order):
                    order, cursor = torch.randperm(len(examples), generator=generator).tolist(), 0
                batch = [examples[i] for i in order[cursor:cursor + args.bs]]
                cursor += len(batch)
                consumed += 1
                length = max(len(row["input_ids"]) for row in batch)
                tensors = {key: torch.tensor([row[key] + [(-100 if key == "labels" else pad if key == "input_ids" else 0)] * (length - len(row[key])) for row in batch], device=device) for key in ("input_ids", "attention_mask", "labels")}
                with autocast():
                    loss = target_loss(model, tensors)
                if not torch.isfinite(loss):
                    raise ValueError("nonfinite training loss")
                if scaler:
                    scaler.scale(loss / accumulation).backward()
                else:
                    (loss / accumulation).backward()
                total_loss += loss.detach().float().item() / accumulation
            if scaler:
                scaler.step(optimizer)  # skips the update if fp16 grads overflowed, then lowers the scale
                scaler.update()
            else:
                optimizer.step()
            if step % 10 == 0 or args.dry_run or step == updates:
                entry = {"step": step, "loss": total_loss}
                if scaler:
                    entry["loss_scale"] = scaler.get_scale()
                if device == "mps":
                    entry["mps_mb"] = round(torch.mps.current_allocated_memory() / 2**20)
                log.write(json.dumps(entry) + "\n")
                log.flush()
    model.save_pretrained(out)
    tokenizer.save_pretrained(out)
    (out / "train_args.json").write_text(json.dumps(dict(vars(args), records=len(records), examples=len(examples), max_length=max(lengths), mean_length=sum(lengths) / len(lengths)), indent=2) + "\n")
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("base", "data", "out"):
        parser.add_argument(f"--{name}", required=True)
    for name, default in (("epochs", 2.0), ("lr", 2e-4)):
        parser.add_argument(f"--{name}", type=float, default=default)
    for name, default in (("rank", 16), ("alpha", 32), ("max_len", 1536), ("bs", 1), ("grad_accum", 8), ("seed", 0)):
        parser.add_argument(f"--{name}", type=int, default=default)
    parser.add_argument("--dry_run", action="store_true")
    parser.add_argument("--precision", choices=("auto", "fp16amp"), default="auto")
    parser.add_argument("--split_gpus", action="store_true")
    train(parser.parse_args())


if __name__ == "__main__":
    main()
