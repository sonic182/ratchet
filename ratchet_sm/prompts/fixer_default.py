FIXER_DEFAULT_PROMPT: str = (
    "You are a data repair assistant."
    " The following text was supposed to match a specific schema"
    " but failed validation.\n\n"
    "Schema:\n{schema}\n\n"
    "Errors:\n{errors}\n\n"
    "Original output:\n{raw}\n\n"
    "Please return only the corrected output in the exact format"
    " required by the schema, with no explanation.\n"
)
