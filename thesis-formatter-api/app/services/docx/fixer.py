"""
Document processing service - Format Fixer.

Fixes document formatting issues based on rules.
Only modifies formatting attributes, never touches text content.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional
import copy

from docx import Document
from docx.shared import Pt, Cm, Twips
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

try:
    from app.services.docx.checker import Issue, Severity, Category
except ImportError:
    # Allow standalone import for testing
    import sys
    import os
    import importlib.util
    
    # Load checker module directly
    checker_path = os.path.join(os.path.dirname(__file__), 'checker.py')
    spec = importlib.util.spec_from_file_location("checker_module", checker_path)
    checker_module = importlib.util.module_from_spec(spec)
    sys.modules["checker_module"] = checker_module
    spec.loader.exec_module(checker_module)
    
    Issue = checker_module.Issue
    Severity = checker_module.Severity
    Category = checker_module.Category


@dataclass
class ChangeRecord:
    """Record of a formatting change made to the document."""

    issue_id: str
    category: str
    location: dict
    before_value: str
    after_value: str
    risk_level: str  # low, medium, high
    timestamp: str

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "issue_id": self.issue_id,
            "category": self.category,
            "location": self.location,
            "before_value": self.before_value,
            "after_value": self.after_value,
            "risk_level": self.risk_level,
            "timestamp": self.timestamp,
        }


class FormatFixer:
    """
    Fixer for document formatting issues.

    Applies fixes to document formatting based on issues found.
    Only modifies formatting attributes, never touches text content.
    """

    # Risk levels for different fix types
    RISK_LEVELS = {
        Category.MARGIN: "low",
        Category.FONT: "medium",
        Category.FONT_SIZE: "low",
        Category.LINE_SPACING: "low",
        Category.PARAGRAPH_SPACING: "low",
        Category.HEADING: "high",
        Category.PAGE_NUMBER: "medium",
        Category.TOC: "medium",
        Category.REFERENCE: "medium",
        Category.INDENT: "low",
    }

    def __init__(self, document: Document, rules: dict):
        """
        Initialize fixer.

        Args:
            document: python-docx Document object.
            rules: Format rules to apply.
        """
        self.document = document
        self.rules = rules
        self.changes: list[ChangeRecord] = []

    def fix_all(self, issues: list[Issue]) -> list[ChangeRecord]:
        """
        Fix all fixable issues.

        Args:
            issues: List of issues to fix.

        Returns:
            List of change records.
        """
        self.changes = []

        for issue in issues:
            if not issue.fixable:
                continue

            try:
                self._fix_issue(issue)
            except Exception as e:
                # Log error but continue with other fixes
                print(f"Failed to fix issue {issue.rule_id}: {e}")

        return self.changes

    def _fix_issue(self, issue: Issue) -> None:
        """Fix a single issue based on its category."""
        fix_handlers = {
            Category.MARGIN: self._fix_margin,
            Category.FONT: self._fix_font,
            Category.FONT_SIZE: self._fix_font_size,
            Category.LINE_SPACING: self._fix_line_spacing,
            Category.PARAGRAPH_SPACING: self._fix_paragraph_spacing,
            Category.HEADING: self._fix_heading,
            Category.INDENT: self._fix_indent,
            Category.REFERENCE: self._fix_reference,
        }

        handler = fix_handlers.get(issue.category)
        if handler:
            handler(issue)

    # ─── Margin Fixes ───

    def _fix_margin(self, issue: Issue) -> None:
        """Fix page margin issue."""
        section_index = issue.location.get("section", 0)
        if section_index >= len(self.document.sections):
            return

        section = self.document.sections[section_index]

        # Parse expected value
        expected_cm = self._parse_cm_value(issue.expected_value)
        if expected_cm is None:
            return

        # Determine which margin to fix
        margin_side = issue.rule_id.split(".")[-1]
        margin_attr = f"{margin_side}_margin"

        # Get current value for change record
        current_margin = getattr(section, margin_attr)
        before_value = f"{self._emu_to_cm(current_margin):.2f}cm" if current_margin else "未设置"

        # Apply fix
        setattr(section, margin_attr, Cm(expected_cm))

        # Record change
        self._record_change(issue, before_value, issue.expected_value)

    # ─── Font Fixes ───

    def _fix_font(self, issue: Issue) -> None:
        """Fix font issue."""
        para_index = issue.location.get("paragraph")
        if para_index is None:
            return

        paragraphs = list(self.document.paragraphs)
        if para_index >= len(paragraphs):
            return

        para = paragraphs[para_index]
        expected_font = issue.expected_value

        # Determine if this is Chinese or English font
        is_chinese = "cn" in issue.rule_id or "中文字体" in issue.suggestion

        before_value = "未设置"
        for run in para.runs:
            if is_chinese:
                # Get current East Asian font
                rPr = run._element.rPr
                if rPr is not None:
                    rFonts = rPr.find(qn('w:rFonts'))
                    if rFonts is not None:
                        before_value = rFonts.get(qn('w:eastAsia'), "未设置")
                        # Set new font
                        rFonts.set(qn('w:eastAsia'), expected_font)
                else:
                    # Create rPr and rFonts if they don't exist
                    rPr = OxmlElement('w:rPr')
                    rFonts = OxmlElement('w:rFonts')
                    rFonts.set(qn('w:eastAsia'), expected_font)
                    rPr.append(rFonts)
                    run._element.insert(0, rPr)
            else:
                # Set ASCII font
                if run.font.name:
                    before_value = run.font.name
                run.font.name = expected_font

        self._record_change(issue, before_value, expected_font)

    def _fix_font_size(self, issue: Issue) -> None:
        """Fix font size issue."""
        para_index = issue.location.get("paragraph")
        if para_index is None:
            return

        paragraphs = list(self.document.paragraphs)
        if para_index >= len(paragraphs):
            return

        para = paragraphs[para_index]
        expected_pt = self._parse_pt_value(issue.expected_value)
        if expected_pt is None:
            return

        before_value = "未设置"
        for run in para.runs:
            if run.font.size:
                before_value = f"{run.font.size.pt:.1f}pt"
            run.font.size = Pt(expected_pt)

        self._record_change(issue, before_value, issue.expected_value)

    # ─── Spacing Fixes ───

    def _fix_line_spacing(self, issue: Issue) -> None:
        """Fix line spacing issue."""
        para_index = issue.location.get("paragraph")
        if para_index is None:
            return

        paragraphs = list(self.document.paragraphs)
        if para_index >= len(paragraphs):
            return

        para = paragraphs[para_index]
        expected_spacing = self._parse_line_spacing_value(issue.expected_value)
        if expected_spacing is None:
            return

        before_value = "未设置"
        pf = para.paragraph_format
        if pf.line_spacing:
            before_value = f"{pf.line_spacing:.1f}倍"

        # Set line spacing
        pf.line_spacing = expected_spacing

        self._record_change(issue, before_value, issue.expected_value)

    def _fix_paragraph_spacing(self, issue: Issue) -> None:
        """Fix paragraph spacing issue."""
        para_index = issue.location.get("paragraph")
        if para_index is None:
            return

        paragraphs = list(self.document.paragraphs)
        if para_index >= len(paragraphs):
            return

        para = paragraphs[para_index]
        expected_pt = self._parse_pt_value(issue.expected_value)
        if expected_pt is None:
            return

        pf = para.paragraph_format
        before_value = "未设置"

        if "before" in issue.rule_id:
            if pf.space_before:
                before_value = f"{pf.space_before.pt:.1f}pt"
            pf.space_before = Pt(expected_pt)
        elif "after" in issue.rule_id:
            if pf.space_after:
                before_value = f"{pf.space_after.pt:.1f}pt"
            pf.space_after = Pt(expected_pt)

        self._record_change(issue, before_value, issue.expected_value)

    # ─── Heading Fixes ───

    def _fix_heading(self, issue: Issue) -> None:
        """Fix heading style issue."""
        para_index = issue.location.get("paragraph")
        if para_index is None:
            return

        paragraphs = list(self.document.paragraphs)
        if para_index >= len(paragraphs):
            return

        para = paragraphs[para_index]

        # Handle different heading issues
        if "font" in issue.rule_id:
            expected_font = issue.expected_value
            before_value = "未设置"

            for run in para.runs:
                rPr = run._element.rPr
                if rPr is not None:
                    rFonts = rPr.find(qn('w:rFonts'))
                    if rFonts is not None:
                        before_value = rFonts.get(qn('w:eastAsia'), "未设置")
                        rFonts.set(qn('w:eastAsia'), expected_font)

            self._record_change(issue, before_value, expected_font)

        elif "bold" in issue.rule_id:
            expected_bold = "加粗" in issue.expected_value
            before_value = "加粗" if para.runs and para.runs[0].font.bold else "未加粗"

            for run in para.runs:
                run.font.bold = expected_bold

            self._record_change(issue, before_value, issue.expected_value)

    # ─── Indent Fixes ───

    def _fix_indent(self, issue: Issue) -> None:
        """Fix paragraph indent issue."""
        para_index = issue.location.get("paragraph")
        if para_index is None:
            return

        paragraphs = list(self.document.paragraphs)
        if para_index >= len(paragraphs):
            return

        para = paragraphs[para_index]
        expected_pt = self._parse_pt_value(issue.expected_value)
        if expected_pt is None:
            return

        pf = para.paragraph_format
        before_value = "未设置"
        if pf.first_line_indent:
            before_value = f"{pf.first_line_indent.pt:.1f}pt"

        pf.first_line_indent = Pt(expected_pt)

        self._record_change(issue, before_value, issue.expected_value)

    # ─── Reference Fixes ───

    def _fix_reference(self, issue: Issue) -> None:
        """Fix reference formatting issue."""
        para_index = issue.location.get("paragraph")
        if para_index is None:
            return

        paragraphs = list(self.document.paragraphs)
        if para_index >= len(paragraphs):
            return

        para = paragraphs[para_index]

        if "indent" in issue.rule_id:
            pf = para.paragraph_format
            before_value = "无悬挂缩进"

            # Set hanging indent (approximately 2 characters = 24pt)
            hanging_indent_pt = 24.0
            pf.first_line_indent = Pt(-hanging_indent_pt)
            pf.left_indent = Pt(hanging_indent_pt)

            self._record_change(issue, before_value, "悬挂缩进")

    # ─── Utility Methods ───

    def _record_change(
        self, issue: Issue, before_value: str, after_value: str
    ) -> None:
        """Record a change made to the document."""
        risk_level = self.RISK_LEVELS.get(issue.category, "medium")

        self.changes.append(ChangeRecord(
            issue_id=issue.rule_id,
            category=issue.category.value,
            location=issue.location,
            before_value=before_value,
            after_value=after_value,
            risk_level=risk_level,
            timestamp=datetime.utcnow().isoformat(),
        ))

    @staticmethod
    def _parse_cm_value(value: str) -> Optional[float]:
        """Parse a value string to centimeters."""
        if not value:
            return None
        value = str(value).strip().lower()
        try:
            if value.endswith("cm"):
                return float(value[:-2])
            elif value.endswith("mm"):
                return float(value[:-2]) / 10
            elif value.endswith("in"):
                return float(value[:-2]) * 2.54
            else:
                return float(value)
        except ValueError:
            return None

    @staticmethod
    def _parse_pt_value(value: str) -> Optional[float]:
        """Parse a value string to points."""
        if not value:
            return None
        value = str(value).strip().lower()
        try:
            if value.endswith("pt"):
                return float(value[:-2])
            elif value.endswith("cm"):
                return float(value[:-2]) / 0.0352778
            elif value.endswith("mm"):
                return float(value[:-2]) / 0.352778
            else:
                return float(value)
        except ValueError:
            return None

    @staticmethod
    def _parse_line_spacing_value(value: str) -> Optional[float]:
        """Parse line spacing value."""
        if not value:
            return None
        value = str(value).strip()
        try:
            if "倍" in value:
                return float(value.replace("倍", "").strip())
            elif value == "单倍":
                return 1.0
            elif value == "1.5倍":
                return 1.5
            elif value == "双倍":
                return 2.0
            else:
                return float(value)
        except ValueError:
            return None

    @staticmethod
    def _emu_to_cm(emu: int) -> float:
        """Convert EMU to centimeters."""
        if emu is None:
            return 0.0
        return emu / 914400 * 2.54
