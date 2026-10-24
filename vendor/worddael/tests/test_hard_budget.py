"""Post-failure engineering regression, not a new independent benchmark.

The frozen 256-character evaluation exposed punctuation growth beyond the
cap. These original synthetic cases test hard budgets, exact offsets, complete
coverage and overlap together, including infeasible punctuation placement.
"""
import random

from worddael import RecursiveChunker, SentenceChunker


def check(text, budget, overlap, cls=RecursiveChunker):
    chunks = cls(max_chars=budget, overlap_chars=overlap).chunk(text)
    cursor = 0
    for chunk in chunks:
        assert 0 < len(chunk.text) <= budget
        assert chunk.text == text[chunk.start:chunk.end]
        assert chunk.start <= cursor < chunk.end
        assert chunk.meta["overlap_chars"] == cursor - chunk.start
        assert 0 <= chunk.meta["overlap_chars"] <= overlap
        cursor = chunk.end
    assert cursor == len(text)
    return chunks


def test_full_chunk_does_not_absorb_closer_beyond_budget():
    text = "甲" * 256 + "，" + "乙" * 300 + "。"
    for overlap in (0, 32):
        check(text, 256, overlap)


def test_opener_does_not_grow_right_neighbor_beyond_budget():
    text = "甲" * 15 + "「" + "乙" * 16 + "」尾"
    for overlap in (0, 5):
        check(text, 16, overlap)


def test_one_character_cap_wins_when_punctuation_cannot_be_balanced():
    text = "甲「乙」，\r\n丙。"
    assert [c.text for c in check(text, 1, 0)] == list(text)


def test_long_atomic_sentence_is_split_without_losing_offsets():
    text = "长" * 1024 + "。"
    for cls in (RecursiveChunker, SentenceChunker):
        check(text, 256, 32, cls)


def test_overlap_is_part_of_final_budget_and_reports_actual_reuse():
    text = ("甲" * 18 + "。" + "乙" * 10 + "。") * 5
    chunks = check(text, 32, 12)
    assert any(c.meta["overlap_chars"] > 0 for c in chunks)


def test_seeded_boundary_stress_invariants():
    rng = random.Random(20261024)
    for budget in (1, 2, 7, 31, 256):
        text = "".join(rng.choice("甲乙Ab１２「」“”，。！？\r\n \u3000") for _ in range(1200))
        for overlap in (0, budget // 3):
            check(text, budget, overlap)
