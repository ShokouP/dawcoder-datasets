"""CPU numerical checks for the new chunked completion objective."""
import unittest
import importlib.util


class CompleteLossTest(unittest.TestCase):
    @unittest.skipUnless(importlib.util.find_spec("torch"), "optional training environment (torch) required")
    def test_chunked_ce_matches_value_and_gradients(self):
        import torch
        from train_sft_complete import chunked_cross_entropy

        torch.manual_seed(12)
        head = torch.nn.Linear(7, 17, bias=False)
        hidden = torch.randn(11, 7, requires_grad=True)
        target = torch.randint(0, 17, (11,))
        expected = torch.nn.functional.cross_entropy(head(hidden), target)
        expected.backward()
        expected_hidden = hidden.grad.clone()
        expected_head = head.weight.grad.clone()
        head.zero_grad()
        hidden.grad = None
        actual = chunked_cross_entropy(head, hidden, target, chunk_size=3)
        actual.backward()
        torch.testing.assert_close(actual, expected)
        torch.testing.assert_close(hidden.grad, expected_hidden)
        torch.testing.assert_close(head.weight.grad, expected_head)

    def test_task_schedule_is_balanced_and_reproducible(self):
        from collections import Counter
        from train_sft_complete import balanced_schedule

        features = [{"task": task} for task, count in (("mix", 10), ("form", 3), ("texture", 7)) for _ in range(count)]
        schedule = balanced_schedule(features, 30, 12)
        self.assertEqual(schedule, balanced_schedule(features, 30, 12))
        self.assertEqual(Counter(features[i]["task"] for i in schedule), {"mix": 10, "form": 10, "texture": 10})
        self.assertEqual(len(set(schedule[:9])), 9)


if __name__ == "__main__":
    unittest.main()
