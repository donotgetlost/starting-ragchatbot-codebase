import anthropic
from typing import List, Optional

class AIGenerator:
    """Handles interactions with Anthropic's Claude API for generating responses"""

    MAX_ROUNDS = 2  # max tool-call rounds before forcing a final synthesis call

    # Static system prompt to avoid rebuilding on each call
    SYSTEM_PROMPT = """ You are an AI assistant specialized in course materials and educational content with access to a comprehensive search tool for course information.

Tool Usage:
- **`search_course_content`**: Use for questions about specific course content or educational material details
- **`get_course_outline`**: Use for any question asking about a course outline, syllabus, lesson list, or course structure
- You may make up to two sequential tool calls when a query requires information from multiple sources (e.g., first retrieve an outline, then search for a topic). Make a second call only when the first result is genuinely insufficient to answer the question completely.
- Synthesize tool results into accurate, fact-based responses
- If a tool yields no results, state this clearly without offering alternatives

When responding to an outline query, always include:
1. The course title
2. The course link (as a clickable URL)
3. Each lesson's number and title, in order

Response Protocol:
- **General knowledge questions**: Answer using existing knowledge without searching
- **Course-specific questions**: Search first, then answer
- **No meta-commentary**:
 - Provide direct answers only — no reasoning process, search explanations, or question-type analysis
 - Do not mention "based on the search results"


All responses must be:
1. **Brief, Concise and focused** - Get to the point quickly
2. **Educational** - Maintain instructional value
3. **Clear** - Use accessible language
4. **Example-supported** - Include relevant examples when they aid understanding
Provide only the direct answer to what was asked.
"""
    
    def __init__(self, api_key: str, model: str, base_url: str = ""):
        client_kwargs = {"api_key": api_key}
        if base_url:
            client_kwargs["base_url"] = base_url
        self.client = anthropic.Anthropic(**client_kwargs)
        self.model = model
        
        # Pre-build base API parameters
        self.base_params = {
            "model": self.model,
            "temperature": 0,
            "max_tokens": 800
        }
    
    def generate_response(self, query: str,
                         conversation_history: Optional[str] = None,
                         tools: Optional[List] = None,
                         tool_manager=None) -> str:
        system_content = (
            f"{self.SYSTEM_PROMPT}\n\nPrevious conversation:\n{conversation_history}"
            if conversation_history
            else self.SYSTEM_PROMPT
        )

        messages = [{"role": "user", "content": query}]
        api_params = {
            **self.base_params,
            "messages": messages,
            "system": system_content
        }
        if tools:
            api_params["tools"] = tools
            api_params["tool_choice"] = {"type": "auto"}

        rounds_used = 0
        while True:
            response = self.client.messages.create(**api_params)

            if response.stop_reason != "tool_use" or not tools or not tool_manager:
                return self._extract_text(response.content)

            messages.append({"role": "assistant", "content": response.content})
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    result = tool_manager.execute_tool(block.name, **block.input)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result
                    })
            messages.append({"role": "user", "content": tool_results})
            rounds_used += 1

            api_params = {**self.base_params, "messages": messages, "system": system_content}
            if rounds_used < self.MAX_ROUNDS:
                api_params["tools"] = tools
                api_params["tool_choice"] = {"type": "auto"}

    def _extract_text(self, content_blocks) -> str:
        for block in content_blocks:
            if block.type == "text":
                return block.text
        return ""