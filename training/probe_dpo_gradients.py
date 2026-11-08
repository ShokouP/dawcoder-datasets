"""Reproduce adapter-switch/checkpoint gradient routing on a tiny CPU network.

Requires torch and peft. Does not load a language model or initialize CUDA.
This isolates a mechanism; it is not a full Qwen training experiment.
"""
import json
import os
from pathlib import Path

os.environ["CUDA_VISIBLE_DEVICES"] = "-1"
os.environ["HF_HUB_OFFLINE"] = "1"


def main():
    import torch
    from peft import LoraConfig, get_peft_model
    from torch.utils.checkpoint import checkpoint

    torch.set_num_threads(2)

    class Tiny(torch.nn.Module):
        def __init__(self):
            super().__init__()
            self.proj = torch.nn.Linear(4, 4, bias=False)

        def forward(self, x):
            return checkpoint(self.proj, x, use_reentrant=True)

    def run(restore_policy):
        torch.manual_seed(7)
        config = LoraConfig(r=2, lora_alpha=4, lora_dropout=0, target_modules=["proj"])
        model = get_peft_model(Tiny(), config, adapter_name="policy")
        model.add_adapter("ref", config)
        model.set_adapter("policy")
        policy = [p for name, p in model.named_parameters() if ".policy." in name]
        opt = torch.optim.SGD(policy, lr=.1)
        before = [p.detach().clone() for p in policy]
        x = torch.ones(1, 4, requires_grad=True, device="cpu")
        output = model(x)
        model.set_adapter("ref")
        with torch.no_grad():
            model(x)
        if restore_policy:
            model.set_adapter("policy")
        output.square().sum().backward()
        result = {
            "policy_grad_tensors": sum(p.grad is not None and p.grad.abs().sum().item() > 0 for p in policy),
            "ref_grad_tensors": sum(p.grad is not None and p.grad.abs().sum().item() > 0
                                    for name, p in model.named_parameters() if ".ref." in name),
        }
        opt.step()
        result["changed_policy_tensors"] = sum(not torch.equal(a, b) for a, b in zip(before, policy))
        return result

    result = {"cpu_only": True, "toy_reproduction_not_full_model": True, "device": "cpu",
              "switch_to_ref_before_backward": run(False), "restore_policy_before_backward": run(True)}
    assert result["switch_to_ref_before_backward"]["changed_policy_tensors"] == 0
    assert result["restore_policy_before_backward"]["changed_policy_tensors"] > 0
    assert result["restore_policy_before_backward"]["ref_grad_tensors"] == 0
    path = Path(__file__).with_name("dpo-gradient-probe.json")
    path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
