from flowstate.text.vocabulary import apply_vocabulary


def test_worked_example_from_plan():
    text = "so i pushed to github and the ci broke"
    result = apply_vocabulary(text)
    assert result == "so i pushed to GitHub and the CI broke"


def test_multi_word_phrase_preferred_over_single_word():
    vocab = {"ci": "CI", "ci cd": "CI/CD"}
    assert apply_vocabulary("set up ci cd pipeline", vocab) == "set up CI/CD pipeline"
    assert apply_vocabulary("check the ci status", vocab) == "check the CI status"


def test_case_insensitive_matching():
    vocab = {"github": "GitHub"}
    assert apply_vocabulary("I use GITHUB daily", vocab) == "I use GitHub daily"
    assert apply_vocabulary("I use GitHub daily", vocab) == "I use GitHub daily"


def test_does_not_touch_unrelated_words():
    vocab = {"api": "API"}
    assert apply_vocabulary("rapid apiary growth", vocab) == "rapid apiary growth"


def test_empty_input_is_noop():
    assert apply_vocabulary("") == ""


def test_does_not_capitalize_or_punctuate():
    # Sentence-level cleanup belongs to the grammar model, not this pass.
    vocab = {"github": "GitHub"}
    result = apply_vocabulary("so i pushed to github", vocab)
    assert result == "so i pushed to GitHub"
    assert not result.endswith(".")
    assert result.startswith("so")
