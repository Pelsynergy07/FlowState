from flowstate.text.guard import preserves_words, repair, salvage_prefix


def test_formatting_edits_are_allowed():
    assert preserves_words("hello this is the full text", "Hello, this is the full text.")
    assert preserves_words("number one milk number two eggs number three bread", "1. Milk\n2. Eggs\n3. Bread")
    assert preserves_words("um I I checked and and saved 60 pages", "I checked and saved 60 pages.")
    assert preserves_words("no paraphrasing what so ever", "No paraphrasing whatsoever.")
    assert preserves_words("it should be under five seconds", "It should be under 5 seconds.")
    assert preserves_words("here are the findings first the dates are wrong next one is that sync fails",
                           "Here are the findings:\n- The dates are wrong\n- Sync fails")
    assert preserves_words("update the README, fix the bug, and send the invoice",
                           "1. Update the README\n2. Fix the bug\n3. Send the invoice")


def test_meaning_changes_are_not_allowed():
    assert not preserves_words("we checked the app", "We verified the app.")
    assert not preserves_words("we checked the app", "They checked the app.")
    assert not preserves_words("sync can fail", "Sync cannot fail.")
    assert not preserves_words("it was ready", "It is ready.")
    assert not preserves_words("ship 123 units tomorrow", "Ship 12 units tomorrow.")
    assert not preserves_words("alpha beta crucial gamma delta", "Alpha beta gamma delta.")
    assert not preserves_words("the app works", "The app work.")
    assert not preserves_words("I want to just have boxes", "I want to have boxes.")
    assert not preserves_words("60. All tests passed", "All tests passed")
    source = " ".join(f"word{i}" for i in range(100))
    assert not preserves_words(source, source.replace("word20 word21", "word21 word20"))
    assert not preserves_words("dear John please review the report",
                               "Dear John, please review the report. Thanks, Pranav.")


def test_repair_restores_words_inside_the_model_layout():
    source = ("hey Johnson hope you're doing great please find attached the file that you are looking for "
              "and then attach this file thanks regards Pranav")
    model = ("Hey Johnson,\n\nHope you're doing great. Please find attached the file you are looking for. "
             "Please attach this file.\n\nRegards,\nPranav")
    result = repair(source, model)
    assert result.startswith("Hey Johnson,\n\nHope you're doing great.")
    assert "the file that you are looking for" in result
    assert "And then attach this file." in result
    assert preserves_words(source, result)


def test_restored_sentence_keeps_its_punctuation_and_list_items_capitals():
    source = "Then we left. I saw the cat. I ate lunch then went home and slept through the whole afternoon"
    model = "Then we left. I ate lunch, then went home and slept through the whole afternoon."
    assert repair(source, model) == (
        "Then we left. I saw the cat. I ate lunch, then went home and slept through the whole afternoon.")
    result = repair("Shopping list to buy tomatoes, onions, beetroots.",
                    "Shopping list to buy:\n- Tomatoes\n- Onions\n- Beetroot")
    assert result.endswith("- Beetroots")


def test_rewrites_are_not_repaired_into_unrelated_layouts():
    assert repair("Review all 300 pages then email John and deploy at 4 pm", "Finish the tasks.") is None
    source = ("I fixed the crash.\n\n1. I have fixed the Qt core startup crash.\n"
              "2. I have upgraded your installed application.")
    model = "I fixed the crash.\n\n1. The Qt core startup crash has been fixed.\n2. Your installed application has been upgraded."
    assert repair(source, model) is None


def test_salvage_uses_finished_sentences_and_appends_the_rest():
    result = salvage_prefix("first sentence here. second sentence is here and third one goes on",
                            "First sentence here. Second sentence is here, and thi")
    assert result == "First sentence here. Second sentence is here and third one goes on"
