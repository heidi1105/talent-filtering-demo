from enrichment.brands.prompt import MIN_EVIDENCE_YEAR, SUBMIT_TOOL, build_system_prompt, build_user_message
from enrichment.brands.provider_base import TalentQuery


def test_system_prompt_explicitly_permits_empty_list():
    prompt = build_system_prompt().lower()
    assert "empty" in prompt
    assert "zero" in prompt


def test_system_prompt_requires_korean_search():
    prompt = build_system_prompt().lower()
    assert "korean" in prompt
    assert "english" in prompt


def test_system_prompt_states_the_evidence_bar():
    prompt = build_system_prompt()
    assert "source_url" in prompt
    assert "evidence_year" in prompt
    assert str(MIN_EVIDENCE_YEAR) in prompt


def test_system_prompt_states_confidence_rubric():
    prompt = build_system_prompt().lower()
    assert "high" in prompt and "medium" in prompt and "low" in prompt
    assert "fan site" in prompt  # low-confidence example from the settled rubric


def test_system_prompt_excludes_not_signed_status():
    prompt = build_system_prompt().lower()
    assert "not signed" in prompt  # mentioned only to say it's not this model's job
    assert "manually" in prompt


def test_user_message_includes_both_english_and_native_name():
    talent = TalentQuery(talent_id="1", name_en="Chaeyoung", name_native="채영",
                          other_names=[], group_name=None, occupation=[], nationality=None)
    msg = build_user_message(talent)
    assert "Chaeyoung" in msg
    assert "채영" in msg


def test_user_message_flags_missing_native_name_rather_than_omitting_it():
    talent = TalentQuery(talent_id="1", name_en="Someone", name_native=None,
                          other_names=[], group_name=None, occupation=[], nationality=None)
    msg = build_user_message(talent)
    assert "not on file" in msg


def test_user_message_includes_optional_fields_when_present():
    talent = TalentQuery(talent_id="1", name_en="Someone", name_native=None,
                          other_names=["Alt Name"], group_name="Group X",
                          occupation=["Singer"], nationality="South Korean")
    msg = build_user_message(talent)
    assert "Alt Name" in msg
    assert "Group X" in msg
    assert "Singer" in msg
    assert "South Korean" in msg


def test_submit_tool_requires_source_url_and_evidence_year():
    required = SUBMIT_TOOL["input_schema"]["properties"]["affiliations"]["items"]["required"]
    assert "source_url" in required
    assert "evidence_year" in required


def test_submit_tool_status_enum_excludes_not_signed():
    status_enum = SUBMIT_TOOL["input_schema"]["properties"]["affiliations"]["items"]["properties"]["status"]["enum"]
    assert set(status_enum) == {"current", "past"}


def test_submit_tool_confidence_enum_matches_rubric():
    confidence_enum = SUBMIT_TOOL["input_schema"]["properties"]["affiliations"]["items"]["properties"]["confidence"]["enum"]
    assert set(confidence_enum) == {"high", "medium", "low"}


def test_submit_tool_affiliations_array_is_not_itself_required_to_be_nonempty():
    # No minItems — an empty array must validate against this schema.
    assert "minItems" not in SUBMIT_TOOL["input_schema"]["properties"]["affiliations"]
