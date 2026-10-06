from flowstate.text.disfluency import clean_disfluencies
from flowstate.text.formatter import needs_polish
from flowstate.text.pipeline import apply_rules
from flowstate.text.structure import structure_text


def test_comma_wrapped_fillers_and_restarts_are_removed():
    source = ("I'm saying a lot of, um, like, I'm trying to, um, um, like, trying to say, you know, like, see, "
              "what I mean.")
    assert clean_disfluencies(source) == "I'm saying a lot of, I'm trying to say, see, what I mean."
    assert clean_disfluencies("It took, like, five minutes.") == "It took five minutes."
    assert clean_disfluencies("Like, I was saying, the build is broken.") == "I was saying, the build is broken."
    assert clean_disfluencies("We need it, so yeah.") == "We need it."
    assert clean_disfluencies("I went to the shop, to the shop, and bought milk.") == "I went to the shop, and bought milk."


def test_meaningful_like_you_know_and_repetition_stay():
    for text in ("I like it. Do you know the answer?", "It looks like a bug.", "Again and again and again.",
                 "It is very very slow. No no, not 60 60 pages.", "pages I mean minutes"):
        assert clean_disfluencies(text) == text


def test_long_prose_gets_paragraphs_at_transitions():
    sentences = [f"The {word} part of this note has a few more words in it." for word in ("opening", "middle", "closing", "final")]
    text = " ".join(sentences) + " Also, here is a new topic with enough words to matter. " + " ".join(sentences)
    result = structure_text(text)
    assert "\n\nAlso, here is a new topic" in result
    assert result.replace("\n\n", " ") == text
    short = "Short note. Also, nothing to split."
    assert structure_text(short) == short


def test_a_spoken_series_becomes_bullets_only_when_a_list_was_asked_for():
    assert apply_rules("Let's add a bullet list. I want to buy a Porsche Macan, a Porsche Cayenne, and a Range Rover.") == (
        "Let's add a bullet list.\n\nI want to buy:\n\n- A Porsche Macan\n- A Porsche Cayenne\n- A Range Rover")
    assert apply_rules("Can you make a list? Pick up the kids, buy groceries, and call mom.") == (
        "Can you make a list?\n\n- Pick up the kids\n- Buy groceries\n- Call mom")
    assert apply_rules("I met John, Sarah, and Mike yesterday.") == "I met John, Sarah, and Mike yesterday."


def test_model_only_runs_when_punctuation_is_missing():
    assert not needs_polish("Hey, bro. Just listen to me. This is a normal punctuated sentence with words.")
    assert needs_polish("so i was thinking we could maybe ship the build tomorrow and then fix the rest next week")
    assert not needs_polish("ok thanks")


def test_requested_series_without_serial_comma_at_the_end_of_a_long_sentence():
    source = ("Let's add a bullet list, right? I wanted a Camry for some reason, I don't want it actually, "
              "I want to buy a Porsche Macan, a Porsche Cayenne and a Range Rover Cullinan. That's it.")
    assert apply_rules(source) == (
        "Let's add a bullet list, right? I wanted a Camry for some reason, I don't want it actually.\n\n"
        "I want to buy:\n\n- A Porsche Macan\n- A Porsche Cayenne\n- A Range Rover Cullinan\n\nThat's it.")
