import unittest
from build import document_group, split_docs
from collect_open_docs import chunk_text, documents, group_key


class CorpusTests(unittest.TestCase):
    def test_chunks_share_split(self):
        docs = [{"source": "new", "doc_id": str(i), "group_key": "book:1", "text_sha256": str(i)} for i in range(20)]
        train, val = split_docs(docs)
        self.assertIn((len(train), len(val)), ((20, 0), (0, 20)))

    def test_original_documents_are_grouped(self):
        self.assertEqual(document_group({"source": "gutenberg-music", "doc_id": "gutenberg-123-001"}), "gutenberg:123")
        a = document_group({"source": "stackexchange-sound", "doc_id": "a1", "url": "https://example.org/q/42#answer"})
        b = document_group({"source": "stackexchange-sound", "doc_id": "q1", "url": "https://example.org/q/42"})
        self.assertEqual(a, b)

    def test_translations_share_group(self):
        spec = {"id": "sonic-pi-tutorial", "repo": "sonic-pi-net/sonic-pi"}
        self.assertEqual(group_key(spec, "etc/doc/tutorial/en/01-Welcome.md"), group_key(spec, "etc/doc/tutorial/zh-Hans/01-Welcome.md"))

    def test_docstrings_are_parsed_without_execution(self):
        text = 'raise RuntimeError("must not execute")\n\ndef example():\n    """' + "Useful MIDI timing documentation. " * 20 + '"""\n    pass\n'
        docs = list(documents("midi.py", text))
        self.assertEqual(len(docs), 1)
        self.assertNotIn("RuntimeError", docs[0][1])

    def test_chunking_preserves_short_tail(self):
        text = "Audio. " * 3000
        parts = chunk_text(text)
        self.assertTrue(all(300 <= len(part) <= 10300 for part in parts))
        self.assertEqual(" ".join(parts).split(), text.split())


if __name__ == "__main__":
    unittest.main()
