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
