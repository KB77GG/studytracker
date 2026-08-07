from scripts.build_toefl_official_v2 import completion_parts, ordered_bank_tokens


def test_ordered_bank_tokens_supports_multiword_chunks_and_distractor():
    assert ordered_bank_tokens(
        "Which countries in Europe are you planning to visit?",
        ["you", "which", "planning", "countries", "in Europe", "are", "plan"],
        "_____ _____ _____ _____ _____ _____ _____ to visit.",
    ) == ["which", "countries", "in Europe", "are", "you", "planning"]


def test_ordered_bank_tokens_ignores_already_spoken_context():
    assert ordered_bank_tokens(
        "Do you want me to send you a copy?",
        ["you want", "of it", "me", "you", "to send", "do", "a copy"],
        "Thanks. _____ _____ _____ _____ _____ _____ _____ ?",
    ) == ["do", "you want", "me", "to send", "you", "a copy"]


def test_completion_parts_recovers_og_prefixes_without_underscore_glyphs():
    display, values = completion_parts(
        "Scientists bel its dec is d to hab destruction.",
        ["believe", "decline", "due", "habitat"],
        1,
    )

    assert display == (
        "Scientists {q01:bel} its {q02:dec} is {q03:d} to {q04:hab} destruction."
    )
    assert values == [("bel", "ieve"), ("dec", "line"), ("d", "ue"), ("hab", "itat")]
