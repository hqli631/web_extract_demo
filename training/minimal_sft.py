"""Finite LoRA SFT smoke; dry-check needs only Python standard library.

Tokenizer mode downloads tokenizer files only. Train mode additionally downloads
weights and requires CUDA; it never executes model-generated Python.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import math
import os
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_rows(path):
    rows = [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]
    if not rows:
        raise ValueError(f"empty dataset: {path}")
    for row in rows:
        messages = row.get("messages", [])
        if [m.get("role") for m in messages] != ["system", "user", "assistant"]:
            raise ValueError("expected exactly system, user, assistant messages")
        if any(not isinstance(m.get("content"), str) or not m["content"].strip() for m in messages):
            raise ValueError("all message content must be nonempty strings")
    return rows


def validate_config(cfg):
    for field in ("max_seq_length", "max_steps", "gradient_accumulation_steps", "lora_r", "max_new_tokens"):
        if not isinstance(cfg[field], int) or cfg[field] <= 0:
            raise ValueError(f"{field} must be a positive integer")
    if not 0 < cfg["learning_rate"] < 1:
        raise ValueError("learning_rate out of range")
    if not cfg["lora_target_modules"]:
        raise ValueError("empty lora target modules")


def require_revision(cfg):
    if not re.fullmatch(r"[0-9a-fA-F]{40}", cfg.get("model_revision") or ""):
        raise ValueError("freeze model_revision as the model repository's 40-character commit SHA first")


def encode_example(tokenizer, row, limit):
    """Verify full-conversation prefix before masking; never silently truncate."""
    messages = row["messages"]
    prompt = tokenizer.apply_chat_template(messages[:-1], tokenize=True, add_generation_prompt=True)
    full = tokenizer.apply_chat_template(messages, tokenize=True, add_generation_prompt=False)
    if full[:len(prompt)] != prompt:
        raise ValueError("chat template prefix mismatch; assistant masking cannot be trusted")
    if len(full) > limit:
        raise ValueError(f"sample length {len(full)} exceeds max_seq_length {limit}; no truncation performed")
    if len(prompt) >= len(full):
        raise ValueError("no supervised assistant tokens")
    return {"input_ids": full, "attention_mask": [1] * len(full),
            "labels": [-100] * len(prompt) + full[len(prompt):]}, len(prompt)


def load_materials(cfg):
    paths = {name: ROOT / cfg[f"{name}_file"] for name in ("train", "dev")}
    rows = {name: load_rows(path) for name, path in paths.items()}
    return paths, rows


def prepare_tokens(cfg, rows):
    require_revision(cfg)
    from transformers import AutoTokenizer
    tokenizer = AutoTokenizer.from_pretrained(cfg["model_id"], revision=cfg["model_revision"], trust_remote_code=False)
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token = tokenizer.eos_token
    encoded, lengths = {}, []
    for split, items in rows.items():
        encoded[split] = []
        for number, row in enumerate(items):
            item, prompt_length = encode_example(tokenizer, row, cfg["max_seq_length"])
            encoded[split].append(item)
            lengths.append({"split": split, "row": number, "total_tokens": len(item["input_ids"]),
                            "prompt_tokens": prompt_length, "supervised_tokens": len(item["input_ids"]) - prompt_length})
    return tokenizer, encoded, lengths


def write_json(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def material_fingerprint(cfg, paths):
    return {"config_sha256": hashlib.sha256(json.dumps(cfg, sort_keys=True).encode()).hexdigest(),
            "data_sha256": {name: digest(path) for name, path in paths.items()}}


def check_preflight(cfg, paths, run_dir):
    path = run_dir / "preflight_manifest.json"
    if not path.exists():
        raise ValueError("run tokenize preflight before weights download")
    if json.loads(path.read_text(encoding="utf-8")) != material_fingerprint(cfg, paths):
        raise ValueError("configuration or data changed since tokenizer preflight; use a new output_dir")


def train(cfg, tokenizer, encoded, lengths, paths, run_dir):
    import torch
    from peft import LoraConfig, get_peft_model
    from transformers import AutoModelForCausalLM, Trainer, TrainerCallback, TrainingArguments, set_seed
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA GPU required for this cloud smoke plan; no CPU fallback")
    if torch.cuda.device_count() != 1:
        raise RuntimeError("expose exactly one GPU with CUDA_VISIBLE_DEVICES=0")
    set_seed(cfg["seed"])
    torch.cuda.reset_peak_memory_stats()
    bf16 = torch.cuda.is_bf16_supported()
    dtype = torch.bfloat16 if bf16 else torch.float16
    model = AutoModelForCausalLM.from_pretrained(
        cfg["model_id"], revision=cfg["model_revision"], trust_remote_code=False,
        torch_dtype=dtype, attn_implementation="sdpa")
    model.config.use_cache = False
    if cfg["max_seq_length"] > model.config.max_position_embeddings:
        raise ValueError("configured training length exceeds model context")
    model = get_peft_model(model, LoraConfig(task_type="CAUSAL_LM", r=cfg["lora_r"],
        lora_alpha=cfg["lora_alpha"], lora_dropout=cfg["lora_dropout"], target_modules=cfg["lora_target_modules"]))
    trainable = {name: param for name, param in model.named_parameters() if param.requires_grad}
    if not trainable:
        raise RuntimeError("no trainable LoRA parameters")
    initial = {name: param.detach().float().cpu().clone() for name, param in trainable.items()}

    class ChangeCheck(TrainerCallback):
        observed_step = 0
        def on_step_end(self, args, state, control, **kwargs):
            self.observed_step = state.global_step

    callback = ChangeCheck()
    # micro-batch one means no padding is required; preserves every label exactly.
    def collate(items):
        if len(items) != 1:
            raise ValueError("this minimum plan supports micro-batch size one only")
        return {name: torch.tensor([items[0][name]], dtype=torch.long) for name in ("input_ids", "attention_mask", "labels")}

    args = TrainingArguments(output_dir=str(run_dir / "checkpoints"), max_steps=cfg["max_steps"],
        per_device_train_batch_size=1, per_device_eval_batch_size=1,
        gradient_accumulation_steps=cfg["gradient_accumulation_steps"], learning_rate=cfg["learning_rate"],
        warmup_steps=0, lr_scheduler_type="constant", optim="adamw_torch", bf16=bf16, fp16=not bf16,
        gradient_checkpointing=True, gradient_checkpointing_kwargs={"use_reentrant": False},
        logging_steps=1, save_strategy="steps", save_steps=cfg["max_steps"], save_total_limit=1,
        report_to=[], seed=cfg["seed"], data_seed=cfg["seed"], remove_unused_columns=False)
    trainer = Trainer(model=model, args=args, train_dataset=encoded["train"],
        eval_dataset=encoded["dev"], data_collator=collate, callbacks=[callback])
    outcome = trainer.train()
    if not math.isfinite(outcome.training_loss):
        raise RuntimeError("non-finite training loss; stop before accepting the smoke run")
    if trainer.state.global_step != cfg["max_steps"] or callback.observed_step == 0:
        raise RuntimeError("expected optimizer steps were not completed")
    changed = {name: float((param.detach().float().cpu() - initial[name]).abs().max()) for name, param in trainable.items()}
    if not any(math.isfinite(delta) and delta > 0 for delta in changed.values()):
        raise RuntimeError("no finite nonzero trainable-parameter delta; smoke did not prove an update")
    if any(not math.isfinite(delta) for delta in changed.values()):
        raise RuntimeError("non-finite LoRA parameter change")
    adapter = run_dir / "adapter"
    trainer.save_model(str(adapter))
    tokenizer.save_pretrained(str(adapter))
    dev = trainer.evaluate()
    proof = {"status": "optimizer_update_observed", "model_id": cfg["model_id"],
        "model_revision": cfg["model_revision"], "optimizer_steps": trainer.state.global_step,
        "trainable_parameters": sum(p.numel() for p in trainable.values()), "parameter_max_abs_delta": changed,
        "train_metrics": outcome.metrics, "dev_loss_historical_only": dev, "token_lengths": lengths,
        "data_sha256": {name: digest(path) for name, path in paths.items()},
        "cuda_device": torch.cuda.get_device_name(), "cuda_version": torch.version.cuda,
        "peak_allocated_bytes": torch.cuda.max_memory_allocated(),
        "peak_reserved_bytes": torch.cuda.max_memory_reserved(),
        "free_total_bytes_after_eval": list(torch.cuda.mem_get_info()),
        "packages": {name: importlib.metadata.version(name) for name in ("torch", "transformers", "peft", "accelerate")},
        "quality_improvement_proven": False, "adapter_reload_verified": False}
    write_json(run_dir / "update_proof.json", proof)
    # Verify serialized adapter tensors, not merely the existence of a directory.
    from safetensors.torch import load_file
    from peft import get_peft_model_state_dict
    saved = load_file(str(adapter / "adapter_model.safetensors"), device="cpu")
    live = get_peft_model_state_dict(model)
    if set(saved) != set(live) or any(not torch.equal(saved[k], live[k].detach().cpu()) for k in saved):
        raise RuntimeError("saved adapter tensors differ from in-memory trained adapter")
    proof["adapter_serialization_verified"] = True
    write_json(run_dir / "update_proof.json", proof)
    print(json.dumps({"adapter": str(adapter), "optimizer_steps": trainer.state.global_step,
                      "quality_improvement_proven": False}, ensure_ascii=False))


def generate(cfg, tokenizer, rows, run_dir, adapter):
    import torch
    from transformers import AutoModelForCausalLM, set_seed
    from peft import PeftModel
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA GPU required for cloud comparison")
    if torch.cuda.device_count() != 1:
        raise RuntimeError("expose exactly one GPU with CUDA_VISIBLE_DEVICES=0")
    if adapter and not Path(adapter).is_dir():
        raise ValueError("adapter must be an existing local directory")
    if adapter:
        if Path(adapter).resolve() != (run_dir / "adapter").resolve() or not (run_dir / "update_proof.json").exists():
            raise ValueError("after-generation must reload this run's trained adapter and update proof")
    set_seed(cfg["seed"])
    dtype = torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16
    model = AutoModelForCausalLM.from_pretrained(cfg["model_id"], revision=cfg["model_revision"],
        torch_dtype=dtype, trust_remote_code=False, attn_implementation="sdpa").to("cuda")
    if adapter:
        model = PeftModel.from_pretrained(model, adapter)
    model.eval()
    outputs = []
    for split, items in rows.items():
        for i, row in enumerate(items):
            prompt = tokenizer.apply_chat_template(row["messages"][:-1], tokenize=False, add_generation_prompt=True)
            tensors = tokenizer(prompt, return_tensors="pt", add_special_tokens=False).to("cuda")
            if tensors.input_ids.shape[-1] + cfg["max_new_tokens"] > model.config.max_position_embeddings:
                raise ValueError("generation exceeds model context")
            with torch.inference_mode():
                answer = model.generate(**tensors, max_new_tokens=cfg["max_new_tokens"], do_sample=False,
                    pad_token_id=tokenizer.pad_token_id)
            ids = answer[0, tensors.input_ids.shape[-1]:]
            text = tokenizer.decode(ids, skip_special_tokens=True)
            outputs.append({"split": split, "row": i, "task_id": row.get("id"),
                "input_sha256": hashlib.sha256(prompt.encode()).hexdigest(), "text": text,
                "new_tokens": len(ids), "may_be_truncated": len(ids) == cfg["max_new_tokens"],
                "automatically_executed": False})
    name = "after_generation.json" if adapter else "before_generation.json"
    write_json(run_dir / name, {"model_revision": cfg["model_revision"], "adapter": adapter,
        "config_sha256": hashlib.sha256(json.dumps(cfg, sort_keys=True).encode()).hexdigest(), "outputs": outputs})
    if adapter and (run_dir / "update_proof.json").exists():
        proof = json.loads((run_dir / "update_proof.json").read_text(encoding="utf-8"))
        proof["adapter_reload_verified"] = True
        write_json(run_dir / "update_proof.json", proof)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("dry-check", "tokenize", "train", "generate"))
    parser.add_argument("--config", default=str(ROOT / "training/minimal_sft.json"))
    parser.add_argument("--adapter", help="local adapter folder for after-generation (generate mode)")
    args = parser.parse_args()
    cfg = json.loads(Path(args.config).read_text(encoding="utf-8"))
    validate_config(cfg)
    paths, rows = load_materials(cfg)
    run_dir = ROOT / cfg["output_dir"]
    if args.mode == "dry-check":
        print(json.dumps({"status": "local_materials_readable", "rows": {k: len(v) for k, v in rows.items()},
            "data_sha256": {k: digest(v) for k, v in paths.items()}, "requires_revision": not bool(cfg.get("model_revision")),
            "gpu_training_tested": False, "no_download_performed": True}, ensure_ascii=False, indent=2))
        return
    tokenizer, encoded, lengths = prepare_tokens(cfg, rows)
    run_dir.mkdir(parents=True, exist_ok=True)
    if args.mode == "tokenize":
        if (run_dir / "preflight_manifest.json").exists():
            check_preflight(cfg, paths, run_dir)
        write_json(run_dir / "token_lengths.json", lengths)
        write_json(run_dir / "frozen_config.json", cfg)
        write_json(run_dir / "preflight_manifest.json", material_fingerprint(cfg, paths))
        print(json.dumps(lengths, indent=2))
    elif args.mode == "train":
        check_preflight(cfg, paths, run_dir)
        if any((run_dir / name).exists() for name in ("update_proof.json", "checkpoints", "adapter")):
            raise ValueError("training run already exists; use a new output_dir rather than overwrite evidence")
        train(cfg, tokenizer, encoded, lengths, paths, run_dir)
    else:
        check_preflight(cfg, paths, run_dir)
        name = "after_generation.json" if args.adapter else "before_generation.json"
        if (run_dir / name).exists():
            raise ValueError("generation evidence already exists; use a new output_dir")
        generate(cfg, tokenizer, rows, run_dir, args.adapter)


if __name__ == "__main__":
    main()
