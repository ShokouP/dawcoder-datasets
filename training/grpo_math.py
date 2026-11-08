"""GRPO token objective and exact chunked token log probabilities."""
import math


def advantages(rewards, std_floor=.02):
    if len(rewards) < 2:
        raise ValueError("GRPO requires at least two completions per prompt")
    mean = sum(rewards) / len(rewards)
    std = math.sqrt(sum((r - mean) ** 2 for r in rewards) / len(rewards))
    return [(r - mean) / max(std, std_floor) for r in rewards], std


def token_objective(new, old, reference, advantage, beta=.05, clip=.2):
    import torch
    ratio = (new - old).exp()
    policy = -torch.minimum(ratio * advantage, ratio.clamp(1 - clip, 1 + clip) * advantage)
    delta = reference - new
    # k3 estimator: exp(delta) - delta - 1; nonnegative, zero at equality.
    kl = (torch.expm1(delta) - delta).clamp(min=0)
    return policy + beta * kl, kl


def token_logps(head, hidden, targets, chunk=128, recompute=False, temperature=1.):
    import torch
    import torch.nn.functional as F
    from torch.utils.checkpoint import checkpoint

    def block(states, labels):
        return -F.cross_entropy(head(states).float() / temperature, labels, reduction="none")

    parts = []
    for start in range(0, len(targets), chunk):
        h, y = hidden[start:start + chunk], targets[start:start + chunk]
        parts.append(checkpoint(block, h, y, use_reentrant=False) if recompute else block(h, y))
    return torch.cat(parts)
