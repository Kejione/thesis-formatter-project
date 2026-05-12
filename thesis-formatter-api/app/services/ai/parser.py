"""
AI Specification Parser.

Parses format specification documents using LLM.
"""

import json
from typing import Optional

from app.services.ai.provider import ModelManager


# System prompt for spec parsing
SYSTEM_PROMPT = """你是一个专业的学术论文格式规范解析专家。你的任务是阅读学校提供的毕业论文格式规范文件，提取出所有与 Word 文档排版相关的格式要求，并输出为结构化 JSON。

你需要提取以下维度的格式规则：
1. 页边距：上、下、左、右边距
2. 字体：中文字体（正文、标题）、英文字体（正文、标题）
3. 字号：正文字号、各级标题字号
4. 行距：正文行距、引用行距等
5. 段间距：段前、段后间距
6. 标题样式：各级标题的字体、字号、加粗、居中等
7. 页码：位置、格式、起始页码
8. 参考文献：缩进格式、编号格式

输出格式要求：
- 严格遵循指定的 JSON Schema
- 所有数值必须带单位（如 "2.5cm"、"12pt"、"1.5倍"）
- 无法确定的字段设为 null
- 只输出 JSON，不要有其他内容"""


# JSON schema for output
OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "school_name": {"type": "string", "description": "学校名称"},
        "thesis_type": {"type": "string", "enum": ["bachelor", "master", "doctor"]},
        "page_margin": {
            "type": "object",
            "properties": {
                "top": {"type": "string"},
                "bottom": {"type": "string"},
                "left": {"type": "string"},
                "right": {"type": "string"},
            },
        },
        "font": {
            "type": "object",
            "properties": {
                "cn_body": {"type": "string", "description": "中文正文字体"},
                "en_body": {"type": "string", "description": "英文正文字体"},
                "cn_title": {"type": "string", "description": "中文标题字体"},
                "en_title": {"type": "string", "description": "英文标题字体"},
            },
        },
        "font_size": {
            "type": "object",
            "properties": {
                "body": {"type": "string"},
                "heading1": {"type": "string"},
                "heading2": {"type": "string"},
                "heading3": {"type": "string"},
            },
        },
        "line_spacing": {
            "type": "object",
            "properties": {
                "body": {"type": "string"},
                "block_quote": {"type": "string"},
            },
        },
        "paragraph_spacing": {
            "type": "object",
            "properties": {
                "body": {
                    "type": "object",
                    "properties": {
                        "before": {"type": "string"},
                        "after": {"type": "string"},
                    },
                },
            },
        },
        "heading_style": {
            "type": "object",
            "properties": {
                "heading1": {
                    "type": "object",
                    "properties": {
                        "font": {"type": "string"},
                        "size": {"type": "string"},
                        "bold": {"type": "boolean"},
                        "center": {"type": "boolean"},
                    },
                },
            },
        },
        "page_number": {
            "type": "object",
            "properties": {
                "position": {"type": "string"},
                "format": {"type": "string"},
                "start_from": {"type": "integer"},
            },
        },
        "references": {
            "type": "object",
            "properties": {
                "indent": {"type": "string"},
                "indent_width": {"type": "string"},
            },
        },
    },
}


class SpecParser:
    """
    Parser for format specification documents.

    Uses LLM to extract structured rules from text.
    """

    def __init__(self, model_manager: ModelManager):
        """
        Initialize parser.

        Args:
            model_manager: Model manager for LLM access.
        """
        self.model_manager = model_manager

    async def parse(
        self,
        text: str,
        model_id: Optional[str] = None,
    ) -> dict:
        """
        Parse specification text into structured rules.

        Args:
            text: Text content from specification document.
            model_id: Optional model ID to use.

        Returns:
            Structured rule dictionary.

        Raises:
            ValueError: If parsing fails.
        """
        # Build prompt
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"请解析以下格式规范：\n\n{text}"},
        ]

        # Call LLM
        response = await self.model_manager.chat_with_fallback(
            messages=messages,
            provider_id=model_id,
            temperature=0.1,
            max_tokens=4096,
        )

        # Parse JSON response
        try:
            # Try to extract JSON from response
            json_str = self._extract_json(response)
            rules = json.loads(json_str)
            return rules
        except json.JSONDecodeError as e:
            raise ValueError(f"Failed to parse LLM response as JSON: {e}")

    def _extract_json(self, text: str) -> str:
        """
        Extract JSON from text that might contain markdown code blocks.

        Args:
            text: Text that may contain JSON.

        Returns:
            Extracted JSON string.
        """
        text = text.strip()

        # Check for markdown code block
        if "```json" in text:
            start = text.find("```json") + 7
            end = text.find("```", start)
            if end > start:
                return text[start:end].strip()
        elif "```" in text:
            start = text.find("```") + 3
            end = text.find("```", start)
            if end > start:
                return text[start:end].strip()

        # Try to find JSON object directly
        if "{" in text and "}" in text:
            start = text.find("{")
            end = text.rfind("}") + 1
            return text[start:end]

        return text
