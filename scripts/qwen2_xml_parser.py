"""vLLM 0.7.3 tool parser for Qwen2.5-Coder's several function-call dialects.

Observed formats:
  <function name="bash" arguments='{"command": "..."}' />     (base model)
  <tool_call>{"name": ..., "arguments": ...}</tool_call>       (chat template)
  <response>{"name": ..., "arguments": ...}</response>         (undertrained SFT)
  ```json {"name": ..., "arguments": ...} ```                  (base model, markdown)
  {"name": ..., "arguments": ...}                              (bare JSON)

Nested ``arguments`` objects break a naive non-greedy ``\\{.*?\\}`` regex, so JSON
objects are extracted with a brace matcher that is string-aware.
"""

import json
import re

from vllm.entrypoints.openai.protocol import (
    ChatCompletionRequest,
    ExtractedToolCallInformation,
    FunctionCall,
    ToolCall,
)
from vllm.entrypoints.openai.tool_parsers.abstract_tool_parser import (
    ToolParser,
    ToolParserManager,
)

_FUNC = re.compile(r'<function\s+name="([^"]+)"\s+arguments=\'(.*?)\'\s*/?>', re.S)
_TAG = re.compile(r"<(tool_call|response)>(.*?)</\1>", re.S)
_FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.S)
_BASH_FENCE = re.compile(r"```(?:bash|sh|shell)\s*(.*?)```", re.S)


def _json_objects(text: str) -> list[str]:
    """All top-level JSON objects in ``text``, respecting strings and escapes."""
    out: list[str] = []
    depth = 0
    start = None
    in_str = False
    esc = False
    for i, ch in enumerate(text):
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            if depth:
                depth -= 1
                if depth == 0 and start is not None:
                    out.append(text[start : i + 1])
                    start = None
    return out


def _normalize_args(args: str) -> str:
    """Return canonical JSON, repairing invalid backslash escapes.

    Undertrained adapters emit e.g. ``\\|`` inside a JSON string, which is not a
    legal JSON escape. Shell alternation needs the backslash, so escaping it is
    the right repair rather than deleting it.
    """
    try:
        return json.dumps(json.loads(args), ensure_ascii=False)
    except json.JSONDecodeError:
        pass
    fixed = re.sub(r'\\(?!["\\/bfnrtu])', r"\\\\", args)
    try:
        return json.dumps(json.loads(fixed), ensure_ascii=False)
    except json.JSONDecodeError:
        return args


def _call_from_json(blob: str) -> ToolCall | None:
    try:
        obj = json.loads(blob)
    except json.JSONDecodeError:
        return None
    if not isinstance(obj, dict) or "name" not in obj:
        return None
    args = obj.get("arguments", {})
    if not isinstance(args, str):
        args = json.dumps(args, ensure_ascii=False)
    return ToolCall(function=FunctionCall(name=str(obj["name"]), arguments=_normalize_args(args)))


def _calls_in(text: str) -> list[ToolCall]:
    calls = []
    for blob in _json_objects(text):
        call = _call_from_json(blob)
        if call is not None:
            calls.append(call)
    return calls


@ToolParserManager.register_module("qwen2_xml")
class Qwen2XmlToolParser(ToolParser):
    def extract_tool_calls(
        self, model_output: str, request: ChatCompletionRequest
    ) -> ExtractedToolCallInformation:
        calls: list[ToolCall] = []
        content = model_output

        # 1. XML function tag with a JSON-string argument.
        for name, args in _FUNC.findall(model_output):
            calls.append(ToolCall(function=FunctionCall(name=name, arguments=_normalize_args(args))))
        if calls:
            content = _FUNC.sub("", model_output).strip()

        # 2. <tool_call> / <response> wrappers.
        if not calls:
            for _, inner in _TAG.findall(model_output):
                calls.extend(_calls_in(inner))
            if calls:
                content = _TAG.sub("", model_output).strip()

        # 3. Markdown fenced JSON.
        if not calls:
            for block in _FENCE.findall(model_output):
                calls.extend(_calls_in(block))
            if calls:
                content = _FENCE.sub("", model_output).strip()

        # 4. Bare JSON object.
        if not calls:
            calls = _calls_in(model_output)
            if calls:
                content = ""

        # 5. A fenced bash block is the base model's way of proposing an action.
        if not calls:
            for block in _BASH_FENCE.findall(model_output):
                command = block.strip()
                if command:
                    calls.append(
                        ToolCall(
                            function=FunctionCall(
                                name="bash",
                                arguments=json.dumps({"command": command}, ensure_ascii=False),
                            )
                        )
                    )
            if calls:
                content = _BASH_FENCE.sub("", model_output).strip()

        if not calls:
            return ExtractedToolCallInformation(
                tools_called=False, tool_calls=[], content=model_output
            )
        return ExtractedToolCallInformation(
            tools_called=True, tool_calls=calls, content=content or None
        )
