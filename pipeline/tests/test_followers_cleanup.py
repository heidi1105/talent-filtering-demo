from enrichment.followers.cleanup import DeadHandle, select_dead_handles


def test_not_found_and_private_are_eligible():
    failures = [
        {"talent_id": "id-1", "name_en": "A", "handle": "a_handle", "status": "not_found"},
        {"talent_id": "id-2", "name_en": "B", "handle": "b_handle", "status": "private"},
    ]
    dead, skipped = select_dead_handles(failures)

    assert [d.handle for d in dead] == ["a_handle", "b_handle"]
    assert skipped == []


def test_error_and_missing_from_response_are_left_alone():
    failures = [
        {"talent_id": "id-1", "name_en": "A", "handle": "a_handle", "status": "error",
         "error_message": "timeout"},
        {"talent_id": "id-2", "name_en": "B", "handle": "b_handle", "status": "missing_from_response",
         "error_message": None},
    ]
    dead, skipped = select_dead_handles(failures)

    assert dead == []
    assert len(skipped) == 2


def test_mixed_failures_split_correctly():
    failures = [
        {"talent_id": "id-1", "name_en": "A", "handle": "a_handle", "status": "not_found"},
        {"talent_id": "id-2", "name_en": "B", "handle": "b_handle", "status": "error"},
        {"talent_id": "id-3", "name_en": "C", "handle": "c_handle", "status": "private"},
    ]
    dead, skipped = select_dead_handles(failures)

    assert {d.handle for d in dead} == {"a_handle", "c_handle"}
    assert len(skipped) == 1
    assert skipped[0]["handle"] == "b_handle"


def test_dead_handle_dataclass_shape():
    dh = DeadHandle(talent_id="id-1", name_en="A", handle="a_handle", status="not_found")
    assert dh.__dict__ == {
        "talent_id": "id-1", "name_en": "A", "handle": "a_handle", "status": "not_found",
    }
