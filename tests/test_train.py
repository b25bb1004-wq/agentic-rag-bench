import json
import math
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from ragbench.train_lora import encode_conversation, target_loss, validate_lengths


class ToyTokenizer:
    """One character per token, with explicit role delimiters."""
    def apply_chat_template(self, messages, tokenize=True, add_generation_prompt=False,
                            enable_thinking=True, return_dict=False):
        text = ''.join(f'<{m["role"]}>{m["content"]}!' for m in messages)
        if add_generation_prompt:
            assert enable_thinking is False
            text += '<assistant>'
        return [ord(c) for c in text]

    def __call__(self, text, add_special_tokens=False):
        assert add_special_tokens is False
        return SimpleNamespace(input_ids=[ord(c) for c in text])


def conversation():
    return [{'role': role, 'content': content} for role, content in
            [('system', 'policy'), ('user', 'question'), ('assistant', 'search'),
             ('user', 'observation'), ('assistant', 'answer')]]


def test_assistant_only_mask():
    tokenizer = ToyTokenizer()
    messages = conversation()
    examples = encode_conversation(tokenizer, messages)
    assert len(examples) == 2
    for example, turn in zip(examples, [2, 4]):
        prompt = tokenizer.apply_chat_template(messages[:turn], add_generation_prompt=True,
                                               enable_thinking=False)
        target = tokenizer(messages[turn]['content'] + '<|im_end|>').input_ids
        assert example['input_ids'] == prompt + target
        assert example['labels'] == [-100] * len(prompt) + target
        assert example['attention_mask'] == [1] * len(example['input_ids'])
    with pytest.raises(AssertionError, match='example would be truncated'):
        encode_conversation(tokenizer, messages, len(examples[-1]['input_ids']) - 1)
    with pytest.raises(ValueError, match='no assistant'):
        encode_conversation(tokenizer, messages[:2])


def test_unstable_template_supported():
    class Unstable(ToyTokenizer):
        def apply_chat_template(self, messages, **kwargs):
            return super().apply_chat_template(messages, **kwargs) + (
                [999] if kwargs.get('add_generation_prompt') else [])
    examples = encode_conversation(Unstable(), conversation())
    assert len(examples) == 2
    for example in examples:
        boundary = example['input_ids'].index(999)
        assert example['labels'][boundary] == -100
        assert example['labels'][boundary + 1] != -100


def test_example_lengths():
    tokenizer = ToyTokenizer()
    messages = conversation()
    examples = encode_conversation(tokenizer, messages)
    lengths = [len(example['input_ids']) for example in examples]
    records = [{'messages': messages}]
    assert validate_lengths(tokenizer, records, max(lengths), examples=examples) == lengths
    with pytest.raises(AssertionError, match='1 examples would be truncated'):
        validate_lengths(tokenizer, records, max(lengths) - 1, examples=examples)
    with pytest.raises(ValueError, match='empty training data'):
        validate_lengths(tokenizer, [], 256, examples=[])


@pytest.fixture
def real_tokenizer():
    local = os.environ.get('RAGBENCH_TOKENIZER')
    if not local or not Path(local).is_dir():
        pytest.skip('RAGBENCH_TOKENIZER must point to an existing local tokenizer directory')
    transformers = pytest.importorskip('transformers')
    return transformers.AutoTokenizer.from_pretrained(local, local_files_only=True)


def test_real_tokenizer_per_turn(real_tokenizer):
    tokenizer = real_tokenizer
    messages = conversation()
    turns = [i for i, message in enumerate(messages) if message['role'] == 'assistant']
    examples = encode_conversation(tokenizer, messages)
    assert len(examples) == len(turns)
    for example, turn in zip(examples, turns):
        prompt = tokenizer.apply_chat_template(messages[:turn], tokenize=False,
                                               add_generation_prompt=True, enable_thinking=False)
        assert prompt.endswith('<|im_start|>assistant\n<think>\n\n</think>\n\n')
        prompt_ids = tokenizer.apply_chat_template(messages[:turn], tokenize=True,
                                                   add_generation_prompt=True, enable_thinking=False,
                                                   return_dict=False)
        assert example['input_ids'][:len(prompt_ids)] == prompt_ids
        assert example['labels'][:len(prompt_ids)] == [-100] * len(prompt_ids)
        target = example['labels'][len(prompt_ids):]
        assert all(label != -100 for label in target)
        assert target == example['input_ids'][len(prompt_ids):]
        assert target[-1] == tokenizer.convert_tokens_to_ids('<|im_end|>')
        assert tokenizer.decode(target, skip_special_tokens=False) == messages[turn]['content'] + '<|im_end|>'
        assert tokenizer.decode(target[:-1], skip_special_tokens=False) == messages[turn]['content']


@pytest.mark.parametrize('batch_size', [1, 2])
@pytest.mark.parametrize('use_peft', [False, True])
def test_target_loss_matches_full_logits(real_tokenizer, batch_size, use_peft):
    torch = pytest.importorskip('torch')
    from transformers import Qwen3Config, Qwen3ForCausalLM

    torch.manual_seed(0)
    model = Qwen3ForCausalLM(Qwen3Config(
        vocab_size=len(real_tokenizer), hidden_size=64, intermediate_size=128,
        num_hidden_layers=2, num_attention_heads=4, num_key_value_heads=2,
        head_dim=16, max_position_embeddings=256, use_cache=False,
    ))
    if use_peft:
        peft = pytest.importorskip('peft')
        model = peft.get_peft_model(model, peft.LoraConfig(
            r=4, lora_alpha=8, target_modules=['q_proj', 'v_proj'],
            task_type='CAUSAL_LM',
        ))
    model.eval()
    examples = encode_conversation(real_tokenizer, conversation())[:batch_size]
    length = max(len(row['input_ids']) for row in examples)
    pad = real_tokenizer.pad_token_id
    if pad is None:
        pad = real_tokenizer.eos_token_id
    tensors = {key: torch.tensor([
        row[key] + [padding] * (length - len(row[key])) for row in examples
    ]) for key, padding in [('input_ids', pad), ('attention_mask', 0), ('labels', -100)]}
    if batch_size == 2:
        assert (tensors['attention_mask'] == 0).any()
    projected = []
    inner = model.get_base_model() if use_peft else model
    hook = inner.lm_head.register_forward_pre_hook(
        lambda module, args: projected.append(args[0].shape))
    try:
        actual = target_loss(model, tensors)
    finally:
        hook.remove()
    assert projected == [(int((tensors['labels'][:, 1:] != -100).sum()), 64)]
    expected = model(**tensors).loss
    torch.testing.assert_close(actual, expected, atol=1e-4, rtol=0)
    if use_peft:
        actual.backward()
        assert any(p.grad is not None and torch.count_nonzero(p.grad)
                   for p in model.parameters() if p.requires_grad)


def test_target_loss_rejects_ignored_batch():
    torch = pytest.importorskip('torch')
    tensors = {'labels': torch.full((2, 4), -100)}
    with pytest.raises(ValueError, match='no supervised target tokens'):
        target_loss(None, tensors)


def test_dry_run(tmp_path):
    local = os.environ.get('RAGBENCH_TOKENIZER')
    if not local or not Path(local).is_dir():
        pytest.skip('RAGBENCH_TOKENIZER must point to an existing local tokenizer directory')
    pytest.importorskip('torch')
    pytest.importorskip('transformers')
    pytest.importorskip('peft')
    from ragbench.train_lora import train
    data = tmp_path / 'sft.jsonl'
    data.write_text(json.dumps({'messages': [{'role': 'system', 'content': 'Answer briefly.'}, {'role': 'user', 'content': 'What is two plus two?'}, {'role': 'assistant', 'content': 'Four.'}, {'role': 'user', 'content': 'Say it again.'}, {'role': 'assistant', 'content': 'Four.'}]}) + '\n')
    out = tmp_path / 'adapter'
    train(SimpleNamespace(base=local, data=str(data), out=str(out), epochs=2, lr=2e-4, rank=4, alpha=8, max_len=256, bs=1, grad_accum=1, seed=0, dry_run=True))
    logs = [json.loads(line) for line in (out / 'train_log.jsonl').read_text().splitlines()]
    assert [entry['step'] for entry in logs] == [1, 2]
    assert all(math.isfinite(entry['loss']) for entry in logs)
    assert all('mps_mb' not in entry for entry in logs)
    assert (out / 'adapter_model.safetensors').is_file()
    assert (out / 'adapter_config.json').is_file()
    saved = json.loads((out / 'train_args.json').read_text())
    assert saved['seed'] == 0
    assert saved['records'] == 1
    assert saved['examples'] == 2
    from transformers import AutoTokenizer
    tokenizer = AutoTokenizer.from_pretrained(local, local_files_only=True)
    records = [json.loads(data.read_text())]
    examples = encode_conversation(tokenizer, records[0]['messages'])
    lengths = [len(example['input_ids']) for example in examples]
    assert saved['max_length'] == max(lengths)
    assert saved['mean_length'] == sum(lengths) / len(lengths)


def test_lora_params_to_fp32_keeps_base_fp16():
    torch = pytest.importorskip('torch')
    pytest.importorskip('peft')
    from transformers import Qwen3Config, Qwen3ForCausalLM
    from peft import LoraConfig, get_peft_model
    from ragbench.train_lora import lora_params_to_fp32
    model = Qwen3ForCausalLM(Qwen3Config(vocab_size=64, hidden_size=32, intermediate_size=64, num_hidden_layers=1,
                                         num_attention_heads=2, num_key_value_heads=1, head_dim=16))
    model = get_peft_model(model, LoraConfig(r=2, lora_alpha=4, target_modules=['q_proj'], task_type='CAUSAL_LM'))
    model.to(dtype=torch.float16)
    lora_params_to_fp32(model)
    trainable = [p for p in model.parameters() if p.requires_grad]
    frozen = [p for p in model.parameters() if not p.requires_grad]
    assert trainable and all(p.dtype == torch.float32 for p in trainable)
    assert frozen and all(p.dtype == torch.float16 for p in frozen)


def test_fp16amp_refuses_without_cuda(tmp_path):
    torch = pytest.importorskip('torch')
    if torch.cuda.is_available():
        pytest.skip('only meaningful without CUDA')
    local = os.environ.get('RAGBENCH_TOKENIZER')
    if not local or not Path(local).is_dir():
        pytest.skip('RAGBENCH_TOKENIZER must point to an existing local tokenizer directory')
    from ragbench.train_lora import train
    data = tmp_path / 'sft.jsonl'
    data.write_text(json.dumps({'messages': [{'role': 'user', 'content': 'Hi'}, {'role': 'assistant', 'content': 'Hello.'}]}) + '\n')
    with pytest.raises(ValueError, match='fp16amp needs a CUDA device'):
        train(SimpleNamespace(base=local, data=str(data), out=str(tmp_path / 'a'), epochs=1, lr=2e-4, rank=4, alpha=8,
                              max_len=256, bs=1, grad_accum=1, seed=0, dry_run=False, precision='fp16amp'))
