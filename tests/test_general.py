from app.general import handle_general_query


def test_general_greeting():
    result = handle_general_query("Hello there")
    assert result["kind"] == "general"
    assert "Hello" in result["answer"]


def test_general_abusive():
    result = handle_general_query("you are stupid")
    assert result["kind"] == "blocked"
    assert "can't help" in result["answer"]
