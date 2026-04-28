# backend/tests/test_ai_generator.py
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

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

    gen.generate_response(query="what is python", tools=[{"name": "search_course_content"}], tool_manager=tool_manager)

    tool_manager.execute_tool.assert_called_once_with("search_course_content", query="python basics")


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
