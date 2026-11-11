import torch
from transformers import AutoModelForCausalLM, BitsAndBytesConfig
from peft import prepare_model_for_kbit_training

path = "/root/paperArts/bench/models/Qwen2.5-Coder-7B-Instruct"
bnb = BitsAndBytesConfig(
    load_in_4bit=True,
    bnb_4bit_quant_type="nf4",
    bnb_4bit_use_double_quant=True,
    bnb_4bit_compute_dtype=torch.bfloat16,
)
m = AutoModelForCausalLM.from_pretrained(
    path, quantization_config=bnb, device_map="auto",
    trust_remote_code=True, attn_implementation="sdpa", torch_dtype=torch.bfloat16,
)
print("loaded:", m.lm_head.weight.dtype, m.model.embed_tokens.weight.dtype)
m = prepare_model_for_kbit_training(m, use_gradient_checkpointing=True)
print("after prepare:", m.lm_head.weight.dtype, m.model.embed_tokens.weight.dtype)
m.lm_head = m.lm_head.to(torch.bfloat16)
m.model.embed_tokens = m.model.embed_tokens.to(torch.bfloat16)
print("after cast:", m.lm_head.weight.dtype, m.model.embed_tokens.weight.dtype)
print("mem:", round(torch.cuda.memory_allocated() / 1e9, 2))
ids = torch.randint(0, 1000, (1, 2501), device="cuda")
out = m(input_ids=ids)
print("logits:", out.logits.dtype, "mem:", round(torch.cuda.memory_allocated() / 1e9, 2))
