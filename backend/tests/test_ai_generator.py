# backend/tests/test_ai_generator.py
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from unittest.mock import MagicMock, patch, call
from ai_generator import AIGenerator


def make_generator():
    with patch("ai_generator.anthropic.Anthropic"):
        gen = AIGenerator(api_key="test-key", model="claude-test")
    return gen


def make_text_response(text):
    block = MagicMock()
    block.type = "text"
    block.text = text
    response = MagicMock()
    response.stop_reason = "end_turn"
    response.content = [block]
    return response


def make_tool_use_response(tool_name, tool_input, tool_id="tool_123"):
    block = MagicMock()
    block.type = "tool_use"
    block.name = tool_name
    block.input = tool_input
    block.id = tool_id
    response = MagicMock()
    response.stop_reason = "tool_use"
    response.content = [block]
    return response


def test_direct_response_returned():
    gen = make_generator()
    gen.client.messages.create.return_value = make_text_response("Hello world")

    result = gen.generate_response(query="hi")

    assert result == "Hello world"


def test_tool_use_triggers_execute_tool():
    gen = make_generator()
    tool_response = make_tool_use_response(
        "search_course_content", {"query": "python basics"}, tool_id="abc"
    )
    final_response = make_text_response("Python is a language.")
    gen.client.messages.create.side_effect = [tool_response, final_response]

    tool_manager = MagicMock()
    tool_manager.execute_tool.return_value = "Some course content"

    gen.generate_response(
        query="what is python",
        tools=[{"name": "search_course_content"}],
        tool_manager=tool_manager,
    )

    tool_manager.execute_tool.assert_called_once_with(
        "search_course_content", query="python basics"
    )


def test_tool_result_sent_as_user_message():
    gen = make_generator()
    tool_response = make_tool_use_response(
        "search_course_content", {"query": "python"}, tool_id="id_99"
    )
    final_response = make_text_response("Answer here.")
    gen.client.messages.create.side_effect = [tool_response, final_response]

    tool_manager = MagicMock()
    tool_manager.execute_tool.return_value = "Chunk of course content"

    gen.generate_response(query="test", tools=[{}], tool_manager=tool_manager)

    assert gen.client.messages.create.call_count == 2
    second_call_kwargs = gen.client.messages.create.call_args_list[1].kwargs
    messages = second_call_kwargs["messages"]
    # Last message must be the tool result sent as user role
    tool_result_message = messages[-1]
    assert tool_result_message["role"] == "user"
    assert tool_result_message["content"][0]["type"] == "tool_result"
    assert tool_result_message["content"][0]["tool_use_id"] == "id_99"
    assert tool_result_message["content"][0]["content"] == "Chunk of course content"


def test_final_response_text_returned():
    gen = make_generator()
    tool_response = make_tool_use_response("search_course_content", {"query": "x"})
    final_response = make_text_response("Final answer.")
    gen.client.messages.create.side_effect = [tool_response, final_response]

    tool_manager = MagicMock()
    tool_manager.execute_tool.return_value = "content"

    result = gen.generate_response(query="test", tools=[{}], tool_manager=tool_manager)

    assert result == "Final answer."


def test_no_tools_means_no_tool_keys_in_api_call():
    gen = make_generator()
    gen.client.messages.create.return_value = make_text_response("ok")

    gen.generate_response(query="general question")

    call_kwargs = gen.client.messages.create.call_args[1]
    assert "tools" not in call_kwargs
    assert "tool_choice" not in call_kwargs


# --- Multi-round tool calling tests ---


def test_two_tool_rounds_then_text_makes_three_api_calls():
    gen = make_generator()
    tool_r1 = make_tool_use_response(
        "get_course_outline", {"course_name": "Python 101"}, tool_id="id_r1"
    )
    tool_r2 = make_tool_use_response(
        "search_course_content", {"query": "closures"}, tool_id="id_r2"
    )
    text_response = make_text_response("Here is your answer.")
    gen.client.messages.create.side_effect = [tool_r1, tool_r2, text_response]

    tool_manager = MagicMock()
    tool_manager.execute_tool.side_effect = ["outline result", "search result"]

    result = gen.generate_response(
        query="multi-step query", tools=[{}], tool_manager=tool_manager
    )

    assert gen.client.messages.create.call_count == 3
    assert tool_manager.execute_tool.call_count == 2
    assert result == "Here is your answer."
    # Tools remain available on call 2 (round 1 is not the last round)
    call2_kwargs = gen.client.messages.create.call_args_list[1].kwargs
    assert "tools" in call2_kwargs
    # Call 3 has tools stripped: rounds_used == MAX_ROUNDS, so cap fires regardless of stop_reason
    call3_kwargs = gen.client.messages.create.call_args_list[2].kwargs
    assert "tools" not in call3_kwargs
    assert "tool_choice" not in call3_kwargs


def test_cap_enforced_strips_tools_on_final_call():
    gen = make_generator()
    gen.MAX_ROUNDS = 1
    tool_r1 = make_tool_use_response(
        "search_course_content", {"query": "python"}, tool_id="cap_id"
    )
    text_response = make_text_response("Capped answer.")
    gen.client.messages.create.side_effect = [tool_r1, text_response]

    tool_manager = MagicMock()
    tool_manager.execute_tool.return_value = "some result"

    result = gen.generate_response(
        query="test cap",
        tools=[{"name": "search_course_content"}],
        tool_manager=tool_manager,
    )

    assert gen.client.messages.create.call_count == 2
    call2_kwargs = gen.client.messages.create.call_args_list[1].kwargs
    assert "tools" not in call2_kwargs
    assert "tool_choice" not in call2_kwargs
    assert result == "Capped answer."


def test_message_accumulation_across_two_rounds():
    gen = make_generator()
    tool_r1 = make_tool_use_response(
        "get_course_outline", {"course_name": "X"}, tool_id="id_r1"
    )
    tool_r2 = make_tool_use_response(
        "search_course_content", {"query": "topic"}, tool_id="id_r2"
    )
    text_response = make_text_response("Final.")
    gen.client.messages.create.side_effect = [tool_r1, tool_r2, text_response]

    tool_manager = MagicMock()
    tool_manager.execute_tool.side_effect = ["outline data", "search data"]

    gen.generate_response(
        query="accumulation test", tools=[{}], tool_manager=tool_manager
    )

    third_call_messages = gen.client.messages.create.call_args_list[2].kwargs[
        "messages"
    ]
    # [user, asst(r1), tool_result(r1), asst(r2), tool_result(r2)]
    assert len(third_call_messages) == 5
    assert third_call_messages[0]["role"] == "user"
    assert third_call_messages[1]["role"] == "assistant"
    assert third_call_messages[2]["role"] == "user"
    assert third_call_messages[2]["content"][0]["tool_use_id"] == "id_r1"
    assert third_call_messages[3]["role"] == "assistant"
    assert third_call_messages[4]["role"] == "user"
    assert third_call_messages[4]["content"][0]["tool_use_id"] == "id_r2"


def test_tool_execution_error_string_passes_through_as_tool_result():
    gen = make_generator()
    tool_response = make_tool_use_response(
        "search_course_content", {"query": "missing"}, tool_id="err_id"
    )
    text_response = make_text_response("Could not find that course.")
    gen.client.messages.create.side_effect = [tool_response, text_response]

    tool_manager = MagicMock()
    tool_manager.execute_tool.return_value = "Search error: collection is empty"

    result = gen.generate_response(
        query="find missing course", tools=[{}], tool_manager=tool_manager
    )

    second_call_messages = gen.client.messages.create.call_args_list[1].kwargs[
        "messages"
    ]
    tool_result_content = second_call_messages[-1]["content"][0]
    assert tool_result_content["type"] == "tool_result"
    assert tool_result_content["content"] == "Search error: collection is empty"
    assert gen.client.messages.create.call_count == 2
    assert result == "Could not find that course."
