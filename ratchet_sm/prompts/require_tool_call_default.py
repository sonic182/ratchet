PSEUDO_CALL_TEMPLATE: str = (
    "A tool invocation was found embedded in the response body (e.g. inside "
    "<tool_call> tags or a fenced block). The system requires the tool call to "
    "be returned in the provider's native structured format, not in the response "
    "text. Please re-issue your response using only a valid structured tool call."
)

NO_TOOL_CALL_TEMPLATE: str = (
    "The response did not contain a tool call. A tool call is required to "
    "continue. Please respond with only a valid structured tool call and no "
    "additional text."
)
