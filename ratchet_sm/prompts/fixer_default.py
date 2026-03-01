FIXER_DEFAULT_PROMPT: str = """You are a data repair assistant.
The following text was supposed to match a specific schema
but failed validation.

Schema:
{schema}

Errors:
{errors}

Original output:
{raw}

Please return only the corrected output in the exact format
required by the schema, with no explanation.
"""
