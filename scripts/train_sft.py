"""QLoRA SFT for the RepoRepair agent trajectories.

Trains a LoRA adapter on ``data/clean/sft.jsonl`` (chat messages with native tool
calls). Only assistant turns are supervised: user prompts and tool outputs are
masked to -100, otherwise the model learns to *generate* observations.

Usage:
    python scripts/train_sft.py \
        --data data/clean/sft.jsonl \
        --model /root/paperArts/bench/models/Qwen2.5-Coder-7B-Instruct \
        --out outputs/sft-qwen-coder-7b \
        --max-seq-len 16384 --epochs 2
"""

from __future__ import annotations

import argparse
import json
import os
import random
from pathlib import Path

import torch
import torch.nn.functional as F
from torch.utils.checkpoint import checkpoint
from datasets import Dataset
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    BitsAndBytesConfig,
    Trainer,
    TrainingArguments,
)

ROOT = Path(__file__).resolve().parents[1]
IGNORE = -100


def load_records(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def split_by_task(records: list[dict], val_ratio: float, seed: int) -> tuple[list[dict], list[dict]]:
    """Split by task id so no task appears in both train and validation."""
    tasks = sorted({r["task_id"] for r in records})
    rng = random.Random(seed)
    rng.shuffle(tasks)
    n_val = max(1, round(len(tasks) * val_ratio))
    val_tasks = set(tasks[:n_val])
    train = [r for r in records if r["task_id"] not in val_tasks]
    val = [r for r in records if r["task_id"] in val_tasks]
    return train, val


def trim_messages(tokenizer, messages: list[dict], max_len: int) -> list[dict]:
    """Keep the task instruction and the most recent steps when a record is too long.

    Dropping the whole record wastes the successful ending; truncating at a token
    boundary can split an assistant tool call from its reply. So keep system+user,
    then add messages from the end until the budget is full, dropping orphan tool
    replies at the seam.
    """
    def length(msgs: list[dict]) -> int:
        text = tokenizer.apply_chat_template(msgs, tokenize=False, add_generation_prompt=False)
        return len(tokenizer(text, add_special_tokens=False)["input_ids"])

    if length(messages) <= max_len:
        return messages

    head = messages[:2]
    tail: list[dict] = []
    for message in reversed(messages[2:]):
        candidate = head + [message] + tail
        if length(candidate) > max_len:
            break
        tail.insert(0, message)
    while tail and tail[0].get("role") == "tool":
        tail.pop(0)
    return head + tail


def encode_example(tokenizer, messages: list[dict], max_len: int) -> dict | None:
    """Tokenize a conversation and label only assistant messages.

    The chat template is rendered incrementally; the token delta for each message
    is attributed to that message, so we know exactly which tokens are assistant
    output (content + tool_calls) versus user/tool input.
    """
    input_ids: list[int] = []
    labels: list[int] = []
    prev_len = 0

    for i, message in enumerate(messages):
        prefix = messages[: i + 1]
        text = tokenizer.apply_chat_template(prefix, tokenize=False, add_generation_prompt=False)
        ids = tokenizer(text, add_special_tokens=False)["input_ids"]
        if len(ids) < prev_len or ids[:prev_len] != input_ids:
            # Templates are prefix-stable for Qwen; bail out rather than mislabel.
            return None
        delta = ids[prev_len:]
        input_ids.extend(delta)
        labels.extend(delta if message.get("role") == "assistant" else [IGNORE] * len(delta))
        prev_len = len(ids)

    if len(input_ids) > max_len:
        return None
    if all(label == IGNORE for label in labels):
        return None

    return {
        "input_ids": input_ids,
        "attention_mask": [1] * len(input_ids),
        "labels": labels,
    }


def _chunk_loss(logits_chunk: torch.Tensor, target_chunk: torch.Tensor) -> torch.Tensor:
    part = logits_chunk.float()
    return F.cross_entropy(
        part.reshape(-1, part.size(-1)),
        target_chunk.reshape(-1),
        ignore_index=IGNORE,
        reduction="sum",
    )


def chunked_cross_entropy(logits: torch.Tensor, labels: torch.Tensor, *, chunk: int = 512) -> torch.Tensor:
    """Cross entropy without materialising a full fp32 copy of the logits.

    ``F.cross_entropy`` upcasts ``[seq, 152k vocab]`` to fp32 at once (~5 GB at 8k
    tokens), which OOMs a 24 GB card. Slicing the sequence keeps the peak at
    ``chunk * vocab * 4`` bytes (~0.6 GB) instead. Each slice is also
    checkpointed: otherwise autograd retains the fp32 copy of *every* slice,
    which costs the same as the full upcast.
    """
    shift_logits = logits[:, :-1, :]
    shift_labels = labels[:, 1:]
    total = logits.new_zeros(())
    count = shift_labels.new_zeros(())
    for start in range(0, shift_logits.size(1), chunk):
        part = shift_logits[:, start : start + chunk, :]
        target = shift_labels[:, start : start + chunk]
        total = total + checkpoint(
            _chunk_loss, part, target, use_reentrant=False
        )
        count = count + (target != IGNORE).sum()
    return total / count.clamp(min=1)


class ChunkedLossTrainer(Trainer):
    def compute_loss(self, model, inputs, return_outputs=False, num_items_in_batch=None):
        labels = inputs.pop("labels")
        outputs = model(**inputs)
        loss = chunked_cross_entropy(outputs.logits, labels)
        return (loss, outputs) if return_outputs else loss


def make_collator(pad_token_id: int):
    def collate(batch: list[dict]) -> dict:
        max_len = max(len(x["input_ids"]) for x in batch)
        out = {"input_ids": [], "attention_mask": [], "labels": []}
        for x in batch:
            pad = max_len - len(x["input_ids"])
            out["input_ids"].append(x["input_ids"] + [pad_token_id] * pad)
            out["attention_mask"].append(x["attention_mask"] + [0] * pad)
            out["labels"].append(x["labels"] + [IGNORE] * pad)
        return {k: torch.tensor(v, dtype=torch.long) for k, v in out.items()}

    return collate


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", default=str(ROOT / "data/clean/sft.jsonl"))
    parser.add_argument("--model", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--max-seq-len", type=int, default=16384)
    parser.add_argument("--epochs", type=float, default=2.0)
    parser.add_argument("--lr", type=float, default=2e-4)
    parser.add_argument("--batch-size", type=int, default=1)
    parser.add_argument("--grad-accum", type=int, default=8)
    parser.add_argument("--val-ratio", type=float, default=0.2)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--max-steps", type=int, default=-1, help="smoke test: stop after N steps")
    args = parser.parse_args()

    os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
    random.seed(args.seed)

    # Prefer memory-efficient attention kernels; the math backend materialises the
    # full attention matrix for every layer and OOMs on a 24 GB card.
    torch.backends.cuda.enable_flash_sdp(True)
    torch.backends.cuda.enable_mem_efficient_sdp(True)
    torch.backends.cuda.enable_math_sdp(False)

    records = load_records(Path(args.data))
    train_records, val_records = split_by_task(records, args.val_ratio, args.seed)
    print(f"records: {len(records)} (train {len(train_records)}, val {len(val_records)})", flush=True)

    tokenizer = AutoTokenizer.from_pretrained(args.model, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    def encode(rows: list[dict]) -> list[dict]:
        encoded = []
        for r in rows:
            messages = trim_messages(tokenizer, r["messages"], args.max_seq_len)
            ex = encode_example(tokenizer, messages, args.max_seq_len)
            if ex is not None:
                encoded.append(ex)
        return encoded

    train_data = encode(train_records)
    val_data = encode(val_records)
    print(f"kept after max_len={args.max_seq_len}: train {len(train_data)}, val {len(val_data)}", flush=True)
    if not train_data:
        raise SystemExit("no training examples fit the context window")

    bnb = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_use_double_quant=True,
        bnb_4bit_compute_dtype=torch.bfloat16,
    )
    model = AutoModelForCausalLM.from_pretrained(
        args.model,
        quantization_config=bnb,
        device_map="auto",
        trust_remote_code=True,
        attn_implementation="sdpa",
        torch_dtype=torch.bfloat16,
    )
    model = prepare_model_for_kbit_training(model, use_gradient_checkpointing=True)
    # prepare_model_for_kbit_training upcasts every non-quantized parameter (lm_head,
    # embeddings, final norm) to fp32 for stability. That costs ~4.4 GB and makes the
    # final hidden state (and therefore logits) fp32; cast them back to bf16.
    model.lm_head = model.lm_head.to(torch.bfloat16)
    model.model.embed_tokens = model.model.embed_tokens.to(torch.bfloat16)
    model.model.norm = model.model.norm.to(torch.bfloat16)
    model.config.use_cache = False

    lora = LoraConfig(
        r=16,
        lora_alpha=32,
        lora_dropout=0.05,
        bias="none",
        task_type="CAUSAL_LM",
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
    )
    model = get_peft_model(model, lora)
    model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={"use_reentrant": False})
    print(f"gradient_checkpointing={model.is_gradient_checkpointing}", flush=True)
    model.print_trainable_parameters()

    train_ds = Dataset.from_list(train_data)
    val_ds = Dataset.from_list(val_data) if val_data else None

    kwargs = dict(
        output_dir=args.out,
        per_device_train_batch_size=args.batch_size,
        per_device_eval_batch_size=1,
        gradient_accumulation_steps=args.grad_accum,
        num_train_epochs=args.epochs,
        max_steps=args.max_steps,
        learning_rate=args.lr,
        lr_scheduler_type="cosine",
        warmup_ratio=0.03,
        bf16=True,
        gradient_checkpointing=True,
        gradient_checkpointing_kwargs={"use_reentrant": False},
        logging_steps=1,
        save_strategy="epoch",
        save_total_limit=2,
        report_to="none",
        optim="paged_adamw_8bit",
        max_grad_norm=1.0,
        seed=args.seed,
        dataloader_num_workers=0,
    )
    # transformers renamed evaluation_strategy -> eval_strategy in 4.46.
    try:
        training_args = TrainingArguments(eval_strategy="epoch", **kwargs)
    except TypeError:
        training_args = TrainingArguments(evaluation_strategy="epoch", **kwargs)

    trainer = ChunkedLossTrainer(
        model=model,
        args=training_args,
        train_dataset=train_ds,
        eval_dataset=val_ds,
        data_collator=make_collator(tokenizer.pad_token_id),
    )
    trainer.train()
    trainer.save_model(args.out)
    tokenizer.save_pretrained(args.out)
    print(f"saved adapter to {args.out}", flush=True)


if __name__ == "__main__":
    main()
