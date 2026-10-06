from flowstate.text.structure import structure_text


def test_email_greeting_body_and_dictated_signature():
    result = structure_text("dear John I wanted to follow up on the budget. Can we meet tomorrow? thanks Pranav")
    assert result == "Dear John,\n\nI wanted to follow up on the budget. Can we meet tomorrow?\n\nThanks,\nPranav"


def test_subject_is_only_added_if_dictated():
    result = structure_text("subject budget update dear John I attached the report. best regards Pranav")
    assert result.startswith("Subject: budget update\n\nDear John,\n\n")
    assert result.endswith("Best regards,\nPranav")
    assert "Subject:" not in structure_text("dear John I attached the report")


def test_bullets_are_one_item_per_line_and_quantities_survive():
    assert structure_text("Shopping: bullet point buy 12 eggs next bullet buy two books next bullet call John") == (
        "Shopping:\n\n- Buy 12 eggs\n- Buy two books\n- Call John"
    )


def test_numbered_items_preserve_full_content():
    assert structure_text("Tasks: number one review all 300 pages number two email John number three deploy at 4 pm") == (
        "Tasks:\n\n1. Review all 300 pages\n2. Email John\n3. Deploy at 4 pm"
    )


def test_single_ordinal_in_plain_prose_is_not_a_list():
    source = "My first meeting is on Tuesday. The number 25 is important."
    assert structure_text(source) == source


def test_paragraph_and_newline_cues():
    assert structure_text("Hello. new paragraph Here is the update. new line More details.") == (
        "Hello. \n\nHere is the update. \nMore details."
    )


def test_spoken_is_after_ordinal_cues_is_not_part_of_items():
    source = ("Here are a couple of things that I want to buy. First is water bottle, second is pencil, "
              "third is banana, and fourth is bed.")
    assert structure_text(source) == (
        "Here are a couple of things that I want to buy.\n\n1. Water bottle\n2. Pencil\n3. Banana\n4. Bed.")
    assert structure_text("Tasks: number one is review the budget, number two is email John") == (
        "Tasks:\n\n1. Review the budget\n2. Email John")


def test_questions_in_a_list_keep_their_is():
    assert structure_text("Questions for the meeting: first, is it working? Second, is there a deadline?") == (
        "Questions for the meeting:\n\n1. Is it working?\n2. Is there a deadline?")


def test_a_second_spoken_list_starts_its_own_numbering():
    source = ("Three things make it unique. First one, point at your screen. Second one, paste anywhere. "
              "Third, is that it runs locally. So how it works is that first, you trigger and speak. "
              "And second, local cleanup. And third, instant paste.")
    assert structure_text(source) == (
        "Three things make it unique.\n\n1. Point at your screen.\n2. Paste anywhere.\n3. It runs locally.\n\n"
        "So how it works is that:\n\n1. You trigger and speak.\n2. Local cleanup.\n3. Instant paste.")


def test_in_order_ordinals_without_a_lead_in_are_a_list_but_dates_and_adjectives_are_not():
    assert structure_text("First check the logs, second restart the server, third tell the team.") == (
        "1. Check the logs\n2. Restart the server\n3. Tell the team.")
    for prose in ("We met on May first, June second, and July third.",
                  "The first draft was fine, the second draft was better, and the third draft shipped."):
        assert structure_text(prose) == prose
