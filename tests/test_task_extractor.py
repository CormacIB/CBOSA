"""
Tests for Issue #9 — TaskExtractor.

Behaviors verified through public interfaces only.
All tests use fixture email bodies (plain strings).
"""
from __future__ import annotations

import pytest

from cbosa.core.task_extractor import TaskExtractor


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def extractor():
    return TaskExtractor()


# ---------------------------------------------------------------------------
# Slice 1 — tracer bullet: empty text → empty list
# ---------------------------------------------------------------------------

def test_empty_text_returns_no_tasks(extractor):
    assert extractor.extract_tasks("") == []


def test_whitespace_only_returns_no_tasks(extractor):
    assert extractor.extract_tasks("   \n\t  ") == []


# ---------------------------------------------------------------------------
# Slice 2 — plain text with no action words → no tasks
# ---------------------------------------------------------------------------

def test_plain_text_no_keywords_returns_no_tasks(extractor):
    assert extractor.extract_tasks("Hello, hope you are well. Have a nice day.") == []


# ---------------------------------------------------------------------------
# Slice 3 — request patterns detected
# ---------------------------------------------------------------------------

def test_please_request_is_extracted(extractor):
    text = "Please send the report by end of day."
    tasks = extractor.extract_tasks(text)
    assert len(tasks) == 1
    assert "Please send the report by end of day." in tasks


def test_can_you_request_is_extracted(extractor):
    text = "Can you review the attached document?"
    tasks = extractor.extract_tasks(text)
    assert any("Can you review the attached document?" in t for t in tasks)


def test_could_you_request_is_extracted(extractor):
    text = "Could you confirm receipt of this email?"
    tasks = extractor.extract_tasks(text)
    assert len(tasks) >= 1


def test_i_need_request_is_extracted(extractor):
    text = "I need your approval before Friday."
    tasks = extractor.extract_tasks(text)
    assert len(tasks) >= 1


# ---------------------------------------------------------------------------
# Slice 4 — deadline keywords detected
# ---------------------------------------------------------------------------

def test_due_keyword_is_extracted(extractor):
    text = "The report is due next Monday."
    tasks = extractor.extract_tasks(text)
    assert len(tasks) >= 1
    assert tasks[0] == "The report is due next Monday."


def test_deadline_keyword_is_extracted(extractor):
    text = "Submission deadline is 2026-05-15."
    tasks = extractor.extract_tasks(text)
    assert len(tasks) >= 1


def test_by_day_of_week_is_extracted(extractor):
    text = "Please complete the form by Friday."
    tasks = extractor.extract_tasks(text)
    assert len(tasks) >= 1


# ---------------------------------------------------------------------------
# Slice 5 — follow-up patterns detected
# ---------------------------------------------------------------------------

def test_follow_up_pattern_extracted(extractor):
    text = "Just wanted to follow up on last week's discussion."
    tasks = extractor.extract_tasks(text)
    assert len(tasks) >= 1


def test_let_me_know_pattern_extracted(extractor):
    text = "Let me know if you have any questions."
    tasks = extractor.extract_tasks(text)
    assert len(tasks) >= 1


def test_rsvp_pattern_extracted(extractor):
    text = "Please RSVP by Thursday."
    tasks = extractor.extract_tasks(text)
    assert len(tasks) >= 1


def test_get_back_to_pattern_extracted(extractor):
    text = "Get back to me when you have a chance."
    tasks = extractor.extract_tasks(text)
    assert len(tasks) >= 1


# ---------------------------------------------------------------------------
# Slice 6 — action verbs at start of line detected
# ---------------------------------------------------------------------------

def test_send_at_line_start_extracted(extractor):
    text = "Send the updated file to the team."
    tasks = extractor.extract_tasks(text)
    assert len(tasks) >= 1


def test_review_at_line_start_extracted(extractor):
    text = "Review the pull request before merging."
    tasks = extractor.extract_tasks(text)
    assert len(tasks) >= 1


def test_submit_at_line_start_extracted(extractor):
    text = "Submit your timesheet by noon."
    tasks = extractor.extract_tasks(text)
    assert len(tasks) >= 1


def test_confirm_at_line_start_extracted(extractor):
    text = "Confirm your attendance at the meeting."
    tasks = extractor.extract_tasks(text)
    assert len(tasks) >= 1


# ---------------------------------------------------------------------------
# Slice 7 — calendar keywords detected
# ---------------------------------------------------------------------------

def test_meeting_keyword_extracted(extractor):
    text = "There is a meeting scheduled for tomorrow at 2pm."
    tasks = extractor.extract_tasks(text)
    assert len(tasks) >= 1


def test_appointment_keyword_extracted(extractor):
    text = "Your appointment has been confirmed."
    tasks = extractor.extract_tasks(text)
    assert len(tasks) >= 1


def test_schedule_keyword_extracted(extractor):
    text = "We need to schedule a call this week."
    tasks = extractor.extract_tasks(text)
    assert len(tasks) >= 1


# ---------------------------------------------------------------------------
# Slice 8 — original text preserved verbatim
# ---------------------------------------------------------------------------

def test_extracted_task_preserves_original_text(extractor):
    original = "Please review the Q1 budget proposal and let me know your thoughts."
    tasks = extractor.extract_tasks(original)
    assert original in tasks


def test_multiline_body_extracts_correct_lines(extractor):
    body = (
        "Hi team,\n"
        "Hope everyone is doing well.\n"
        "Please review the attached slides before our meeting tomorrow.\n"
        "Looking forward to seeing you all.\n"
        "Best regards"
    )
    tasks = extractor.extract_tasks(body)
    assert any("Please review the attached slides" in t for t in tasks)
    assert not any("Hope everyone is doing well" in t for t in tasks)


# ---------------------------------------------------------------------------
# Slice 9 — duplicates are deduplicated
# ---------------------------------------------------------------------------

def test_duplicate_sentences_deduplicated(extractor):
    text = "Please send the report.\nPlease send the report."
    tasks = extractor.extract_tasks(text)
    assert tasks.count("Please send the report.") == 1


# ---------------------------------------------------------------------------
# Slice 10 — multi-sentence email body realistic fixture
# ---------------------------------------------------------------------------

def test_realistic_email_extracts_multiple_tasks(extractor):
    email_body = """
Hi Sarah,

Following up on our conversation from last week.

Could you send me the updated project timeline by Wednesday?
The deadline for the client deliverable is May 20th.
Let me know if you need any additional resources.

We have a meeting scheduled for Friday at 3pm to review progress.

Best,
John
"""
    tasks = extractor.extract_tasks(email_body)
    assert len(tasks) >= 3  # at least: "could you", "deadline", "let me know" + "meeting"


def test_non_action_lines_not_extracted(extractor):
    body = "Hi John,\nThank you for your message.\nBest regards,\nAlice"
    tasks = extractor.extract_tasks(body)
    assert tasks == []
