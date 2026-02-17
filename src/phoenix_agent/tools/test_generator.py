from __future__ import annotations
import logging
from pathlib import Path

from phoenix_agent.config import PhoenixConfig
from phoenix_agent import llm_json
from phoenix_agent.provider import create_llm
from phoenix_agent.tools.base import BaseTool, ToolCategory, ToolResult

logger = logging.getLogger(__name__)


class TestGeneratorTool(BaseTool):
    name = "test_generator"
    description = "Generate unit tests for a given code file."
    category = ToolCategory.TESTING
    parameters_schema = {
        "required": ["file_path"],
        "properties": {
            "file_path": {"type": "string", "description": "The path to the file to generate tests for."}
        },
    }

    def __init__(self, config: PhoenixConfig):
        self.config = config

    def execute(self, file_path: str, **kwargs) -> ToolResult:
        try:
            source_path = Path(file_path)
            source_code = source_path.read_text()

            prompt = self._create_prompt(source_code)
            
            llm = create_llm(self.config)
            llm_response = llm.invoke(prompt)
            
            test_code = self._extract_code(llm_response.content)

            test_file_path = self._get_test_file_path(source_path)
            test_file_path.parent.mkdir(parents=True, exist_ok=True)
            test_file_path.write_text(test_code)

            return ToolResult(
                success=True,
                output={"test_file_path": str(test_file_path)},
                metadata={"lines_generated": len(test_code.splitlines())},
            )
        except Exception as e:
            logger.exception(f"Failed to generate tests for {file_path}: {e}")
            return ToolResult(success=False, error=str(e))

    def _create_prompt(self, source_code: str) -> str:
        return f"""
You are an expert Python programmer specializing in writing unit tests.
Your task is to write a comprehensive suite of unit tests for the following Python code, using the pytest framework.

**Instructions:**
1.  **Import necessary libraries.** You will likely need to import `pytest` and the modules from the code you are testing.
2.  **Cover edge cases.** Think about empty inputs, invalid inputs, and other edge cases.
3.  **Use meaningful test names.** The test names should clearly describe what they are testing.
4.  **Do not use mock objects** unless absolutely necessary. The tests should be as simple and direct as possible.
5.  **Output ONLY the test code.** Do not include any explanations, comments, or other text outside of the Python code block.

**Source Code to Test:**
```python
{source_code}
```

**Generated Pytest Code:**
"""

    def _extract_code(self, response: str) -> str:
        # Simple extraction, assuming the LLM follows instructions and only outputs code
        if "```python" in response:
            return response.split("```python")[1].split("```")[0].strip()
        return response.strip()

    def _get_test_file_path(self, source_path: Path) -> Path:
        # Place tests in a parallel `tests` directory
        # e.g., src/foo/bar.py -> tests/foo/test_bar.py
        
        parts = list(source_path.parts)
        if "src" in parts:
            src_index = parts.index("src")
            test_parts = ["tests"] + parts[src_index+1:]
        else:
            # Not in a src layout, assume tests are in a sibling dir
            test_parts = ["tests"] + parts[1:]

        test_filename = f"test_{source_path.name}"
        return Path(source_path.parent.parent, *test_parts[:-1], test_filename)

