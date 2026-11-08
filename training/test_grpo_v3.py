import copy
import importlib.util
import json
from pathlib import Path
import unittest

from grpo_math import advantages
from grpo_reward import score


class RewardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = [json.loads(line) for line in (Path(__file__).parent / "data/dawcoder_sft_train.jsonl").read_text(encoding="utf-8").splitlines()]

    def test_every_gold_has_unit_reward(self):
        for row in self.rows:
            instruction = json.loads(row["instruction"])
            result = score(row["task"], instruction["state"], json.loads(row["output"]), row["output"])
            self.assertTrue(result["valid"])
            self.assertAlmostEqual(result["reward"], 1.)

    def test_parameter_mistakes_do_not_get_full_reward(self):
        checked = set()
        for row in self.rows:
            if row["task"] != "mix":
                continue
            gold = json.loads(row["output"])
            kind = gold["ops"][0]["op"]
            if kind in checked or kind not in ("set_eq", "set_comp", "set_send"):
                continue
            pred = copy.deepcopy(gold)
            op = pred["ops"][0]
            if kind == "set_eq":
                op["freq"] = 20000 if op["freq"] < 10000 else 20
                op["gain_db"] = -op["gain_db"] or 6
            elif kind == "set_comp":
                op["params"]["ratio"] = 20 if op["params"]["ratio"] < 10 else 1
            else:
                op["gain_db"] = -60 if op["gain_db"] > -40 else 0
            result = score("mix", json.loads(row["instruction"])["state"], gold, json.dumps(pred))
            self.assertTrue(result["valid"])
            self.assertLess(result["reward"], .999)
            checked.add(kind)
        self.assertEqual(checked, {"set_eq", "set_comp", "set_send"})

    def test_compact_texture_is_valid_for_all_styles(self):
        from train_grpo_v3 import compact_texture
        from patch_validation import validate
        styles = set()
        for row in self.rows:
            if row["task"] != "texture":
                continue
            compact = compact_texture(row)
            state = json.loads(compact["instruction"])["state"]
            gold = json.loads(compact["output"])
            self.assertEqual(state["bars"], 2)
            self.assertEqual(len(state["progression"]), 1)
            self.assertTrue(validate("texture", state, gold)[0])
            styles.add(state["style"])
        self.assertEqual(len(styles), 5)

    def test_group_advantages_and_zero_variance(self):
        adv, std = advantages([1., 0., 1., 0.])
        self.assertEqual(adv, [1., -1., 1., -1.])
        self.assertEqual(std, .5)
        self.assertEqual(advantages([1.] * 4)[0], [0.] * 4)
        with self.assertRaises(ValueError):
            advantages([1.])


@unittest.skipUnless(importlib.util.find_spec("torch"), "optional training environment required")
class GradientTests(unittest.TestCase):
    def test_grpo_update_favors_rewarded_action(self):
        import torch
        from grpo_math import token_objective
        logits = torch.nn.Parameter(torch.zeros(2))
        optimizer = torch.optim.SGD([logits], lr=.1)
        selected = torch.tensor([0, 1, 0, 1])
        new = torch.log_softmax(logits, -1)[selected]
        adv = torch.tensor(advantages([1., 0., 1., 0.])[0])
        loss, kl = token_objective(new, new.detach(), new.detach(), adv)
        self.assertTrue(torch.equal(kl, torch.zeros_like(kl)))
        loss.mean().backward()
        optimizer.step()
        self.assertGreater(torch.softmax(logits, -1)[0].item(), .5)

    def test_k3_nonnegative(self):
        import torch
        from grpo_math import token_objective
        new = torch.tensor([-2., -1., -.1])
        _, kl = token_objective(new, new, torch.tensor([-1., -2., -.1]), 0.)
        self.assertTrue(bool((kl >= 0).all()))
        self.assertEqual(kl[-1], 0.)

    def test_chunked_logps_and_gradients_match(self):
        import torch
        from grpo_math import token_logps
        torch.manual_seed(10)
        head = torch.nn.Linear(5, 19, bias=False)
        hidden = torch.randn(13, 5, requires_grad=True)
        target = torch.randint(0, 19, (13,))
        expected = torch.log_softmax(head(hidden) / .8, -1).gather(1, target[:, None]).squeeze(1)
        expected.sum().backward()
        hidden_grad, head_grad = hidden.grad.clone(), head.weight.grad.clone()
        hidden.grad = None
        head.zero_grad()
        actual = token_logps(head, hidden, target, chunk=4, recompute=True, temperature=.8)
        actual.sum().backward()
        torch.testing.assert_close(actual, expected)
        torch.testing.assert_close(hidden.grad, hidden_grad)
        torch.testing.assert_close(head.weight.grad, head_grad)


if __name__ == "__main__":
    unittest.main()
