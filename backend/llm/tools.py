"""Shared tool definitions for AI Analyst providers."""

TOOLS = [
    {
        "name": "read_file",
        "description": (
            "Read a source file from the BESS Manager codebase.  Returns the "
            "file contents with line numbers.  For large files, use start_line "
            "and end_line to read a specific range."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": (
                        "Relative path from the project root, e.g. "
                        "'core/bess/dp_battery_algorithm.py' or 'backend/api.py'."
                    ),
                },
                "start_line": {
                    "type": "integer",
                    "description": "First line to read (1-based).  Omit to start from line 1.",
                },
                "end_line": {
                    "type": "integer",
                    "description": "Last line to read (1-based).  Omit to read to end of file.",
                },
            },
            "required": ["path"],
        },
    },
    {
        "name": "search_code",
        "description": (
            "Search the BESS Manager codebase for a regex pattern.  Returns "
            "matching lines with file paths and line numbers.  Use to find "
            "functions, variables, error messages, or trace code paths."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "Regex pattern to search for, e.g. 'cost_basis' or 'def optimize_.*schedule'.",
                },
                "file_glob": {
                    "type": "string",
                    "description": "Optional glob to filter files, e.g. '*.py' or 'core/bess/*.py'.  Default: '*.py'.",
                },
            },
            "required": ["pattern"],
        },
    },
    {
        "name": "list_files",
        "description": (
            "List source files in a directory of the BESS Manager codebase.  "
            "Returns file names with sizes.  Useful for understanding project "
            "structure before reading specific files."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": (
                        "Relative directory path, e.g. 'core/bess/' or 'backend/'.  "
                        "Omit or use '' for the project root."
                    ),
                },
            },
        },
    },
]
