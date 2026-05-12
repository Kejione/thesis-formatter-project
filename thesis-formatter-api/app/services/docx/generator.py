"""
Document processing service - Generator.

Generates fixed documents and change logs.
"""

from datetime import datetime
from io import BytesIO
from typing import Optional
import os

from docx import Document

try:
    from app.services.docx.fixer import ChangeRecord
except ImportError:
    # Allow standalone import for testing
    import sys
    import os
    import importlib.util
    
    # Load fixer module directly
    fixer_path = os.path.join(os.path.dirname(__file__), 'fixer.py')
    spec = importlib.util.spec_from_file_location("fixer_module", fixer_path)
    fixer_module = importlib.util.module_from_spec(spec)
    sys.modules["fixer_module"] = fixer_module
    spec.loader.exec_module(fixer_module)
    
    ChangeRecord = fixer_module.ChangeRecord


class DocxGenerator:
    """
    Generator for fixed documents and change logs.

    Handles saving fixed documents and generating change reports.
    """

    def __init__(self, document: Document, original_filename: str):
        """
        Initialize generator.

        Args:
            document: python-docx Document object (after fixes applied).
            original_filename: Original document filename.
        """
        self.document = document
        self.original_filename = original_filename

    def save_fixed_document(self, output_path: str) -> str:
        """
        Save the fixed document to a file.

        Args:
            output_path: Path to save the document.

        Returns:
            Path to the saved document.
        """
        self.document.save(output_path)
        return output_path

    def get_document_bytes(self) -> bytes:
        """
        Get the fixed document as bytes.

        Returns:
            Document content as bytes.
        """
        buffer = BytesIO()
        self.document.save(buffer)
        buffer.seek(0)
        return buffer.getvalue()

    def generate_change_log_markdown(
        self, changes: list[ChangeRecord], document_info: dict
    ) -> str:
        """
        Generate a markdown change log.

        Args:
            changes: List of change records.
            document_info: Document metadata (title, page_count, etc.).

        Returns:
            Markdown formatted change log.
        """
        lines = [
            "# 格式修改记录",
            "",
            f"**文档名称**: {self.original_filename}",
            f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"**修改数量**: {len(changes)} 处",
            "",
        ]

        # Add document info
        if document_info:
            lines.append("## 文档信息")
            lines.append("")
            if document_info.get("title"):
                lines.append(f"- **标题**: {document_info['title']}")
            if document_info.get("page_count"):
                lines.append(f"- **页数**: {document_info['page_count']}")
            if document_info.get("word_count"):
                lines.append(f"- **字数**: {document_info['word_count']}")
            lines.append("")

        # Group changes by category
        categories = {}
        for change in changes:
            cat = change.category
            if cat not in categories:
                categories[cat] = []
            categories[cat].append(change)

        # Category labels
        category_labels = {
            "margin": "页边距",
            "font": "字体",
            "font_size": "字号",
            "line_spacing": "行距",
            "paragraph_spacing": "段间距",
            "heading": "标题",
            "page_number": "页码",
            "toc": "目录",
            "reference": "参考文献",
            "indent": "缩进",
        }

        # Risk level labels
        risk_labels = {
            "low": "🟢 低风险",
            "medium": "🟡 中风险",
            "high": "🔴 高风险",
        }

        # Add changes by category
        lines.append("## 修改详情")
        lines.append("")

        for category, cat_changes in categories.items():
            cat_label = category_labels.get(category, category)
            lines.append(f"### {cat_label}")
            lines.append("")

            for i, change in enumerate(cat_changes, 1):
                risk_label = risk_labels.get(change.risk_level, change.risk_level)
                location_str = self._format_location(change.location)

                lines.append(f"#### {i}. {change.issue_id}")
                lines.append("")
                lines.append(f"- **位置**: {location_str}")
                lines.append(f"- **修改前**: {change.before_value}")
                lines.append(f"- **修改后**: {change.after_value}")
                lines.append(f"- **风险等级**: {risk_label}")
                lines.append(f"- **修改时间**: {change.timestamp}")
                lines.append("")

        # Add summary
        lines.append("## 修改统计")
        lines.append("")
        lines.append("| 类别 | 数量 |")
        lines.append("|------|------|")
        for category, cat_changes in categories.items():
            cat_label = category_labels.get(category, category)
            lines.append(f"| {cat_label} | {len(cat_changes)} |")
        lines.append("")

        # Add risk summary
        risk_counts = {"low": 0, "medium": 0, "high": 0}
        for change in changes:
            risk_counts[change.risk_level] = risk_counts.get(change.risk_level, 0) + 1

        lines.append("### 风险等级分布")
        lines.append("")
        lines.append(f"- {risk_labels['low']}: {risk_counts['low']} 处")
        lines.append(f"- {risk_labels['medium']}: {risk_counts['medium']} 处")
        lines.append(f"- {risk_labels['high']}: {risk_counts['high']} 处")
        lines.append("")

        # Add notes
        lines.append("## 注意事项")
        lines.append("")
        lines.append("1. 本次修改仅涉及格式调整，未改动任何文本内容。")
        lines.append("2. 高风险修改建议人工复核确认。")
        lines.append("3. 建议在 Word 中检查目录和页码是否需要更新。")
        lines.append("")

        return "\n".join(lines)

    def generate_report_markdown(
        self,
        issues: list,
        changes: list[ChangeRecord],
        document_info: dict,
        rules: dict,
    ) -> str:
        """
        Generate a comprehensive format check report.

        Args:
            issues: List of all issues found.
            changes: List of changes made.
            document_info: Document metadata.
            rules: Rules used for checking.

        Returns:
            Markdown formatted report.
        """
        lines = [
            "# 格式检查报告",
            "",
            f"**文档名称**: {self.original_filename}",
            f"**检查时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
        ]

        # Summary
        error_count = sum(1 for i in issues if i.severity.value == "error")
        warning_count = sum(1 for i in issues if i.severity.value == "warning")
        info_count = sum(1 for i in issues if i.severity.value == "info")

        lines.append("## 检查结果概览")
        lines.append("")
        lines.append(f"- ❌ **错误**: {error_count} 处")
        lines.append(f"- ⚠️ **警告**: {warning_count} 处")
        lines.append(f"- ℹ️ **提示**: {info_count} 处")
        lines.append(f"- ✅ **已修复**: {len(changes)} 处")
        lines.append("")

        # Document info
        if document_info:
            lines.append("## 文档信息")
            lines.append("")
            for key, value in document_info.items():
                if value:
                    lines.append(f"- **{key}**: {value}")
            lines.append("")

        # Rules used
        if rules:
            lines.append("## 使用的格式规则")
            lines.append("")
            if rules.get("school_name"):
                lines.append(f"- **学校**: {rules['school_name']}")
            if rules.get("thesis_type"):
                thesis_type_map = {"bachelor": "本科", "master": "硕士", "doctor": "博士"}
                lines.append(f"- **论文类型**: {thesis_type_map.get(rules['thesis_type'], rules['thesis_type'])}")
            lines.append("")

        # Issues by category
        lines.append("## 问题详情")
        lines.append("")

        category_labels = {
            "margin": "页边距",
            "font": "字体",
            "font_size": "字号",
            "line_spacing": "行距",
            "paragraph_spacing": "段间距",
            "heading": "标题",
            "page_number": "页码",
            "toc": "目录",
            "reference": "参考文献",
            "indent": "缩进",
        }

        # Group issues by category
        issues_by_category = {}
        for issue in issues:
            cat = issue.category.value
            if cat not in issues_by_category:
                issues_by_category[cat] = []
            issues_by_category[cat].append(issue)

        for category, cat_issues in issues_by_category.items():
            cat_label = category_labels.get(category, category)
            lines.append(f"### {cat_label}")
            lines.append("")

            for issue in cat_issues:
                severity_icon = {
                    "error": "❌",
                    "warning": "⚠️",
                    "info": "ℹ️",
                }.get(issue.severity.value, "•")

                location_str = self._format_location(issue.location)
                lines.append(f"{severity_icon} **{location_str}**")
                lines.append(f"   - 当前值: {issue.current_value}")
                lines.append(f"   - 期望值: {issue.expected_value}")
                lines.append(f"   - 建议: {issue.suggestion}")
                lines.append("")

        return "\n".join(lines)

    def _format_location(self, location: dict) -> str:
        """Format location dict to readable string."""
        parts = []
        if location.get("page"):
            parts.append(f"第{location['page']}页")
        if location.get("paragraph"):
            parts.append(f"第{location['paragraph']}段")
        if location.get("section"):
            parts.append(f"第{location['section']}节")
        return " ".join(parts) if parts else "全文"
