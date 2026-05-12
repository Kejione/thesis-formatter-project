"""
Document processing service - Format Checker.

Checks document formatting against rules and generates issues.
Supports: page margins, fonts, font sizes, line spacing, paragraph spacing,
heading styles, page numbers, table of contents, and references.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional
import re

try:
    from app.services.docx.parser import (
        DocumentInfo,
        ParagraphInfo,
        SectionInfo,
        HeaderFooterInfo,
        TOCInfo,
        ElementType,
    )
except ImportError:
    # Allow standalone import for testing
    import sys
    import os
    import importlib.util
    
    # Load parser module directly
    parser_path = os.path.join(os.path.dirname(__file__), 'parser.py')
    spec = importlib.util.spec_from_file_location("parser_module", parser_path)
    parser_module = importlib.util.module_from_spec(spec)
    sys.modules["parser_module"] = parser_module
    spec.loader.exec_module(parser_module)
    
    DocumentInfo = parser_module.DocumentInfo
    ParagraphInfo = parser_module.ParagraphInfo
    SectionInfo = parser_module.SectionInfo
    HeaderFooterInfo = parser_module.HeaderFooterInfo
    TOCInfo = parser_module.TOCInfo
    ElementType = parser_module.ElementType


class Severity(str, Enum):
    """Issue severity levels."""
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class Category(str, Enum):
    """Issue category types."""
    MARGIN = "margin"
    FONT = "font"
    FONT_SIZE = "font_size"
    LINE_SPACING = "line_spacing"
    PARAGRAPH_SPACING = "paragraph_spacing"
    HEADING = "heading"
    PAGE_NUMBER = "page_number"
    TOC = "toc"
    REFERENCE = "reference"
    INDENT = "indent"


@dataclass
class Issue:
    """A format issue found in the document."""

    severity: Severity
    category: Category
    location: dict  # {page, paragraph, section}
    rule_id: str
    current_value: str
    expected_value: str
    suggestion: str
    fixable: bool = True  # Whether this issue can be auto-fixed

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "severity": self.severity.value,
            "category": self.category.value,
            "location": self.location,
            "rule_id": self.rule_id,
            "current_value": self.current_value,
            "expected_value": self.expected_value,
            "suggestion": self.suggestion,
            "fixable": self.fixable,
        }


class FormatChecker:
    """
    Checker for document formatting.

    Compares document formatting against rules and generates issues.
    """

    # Tolerance for numerical comparisons
    MARGIN_TOLERANCE_CM = 0.1
    FONT_SIZE_TOLERANCE_PT = 0.5
    SPACING_TOLERANCE_PT = 1.0
    LINE_SPACING_TOLERANCE = 0.1

    def __init__(self, document_info: DocumentInfo, rules: dict):
        """
        Initialize checker.

        Args:
            document_info: Parsed document information.
            rules: Format rules to check against.
        """
        self.document_info = document_info
        self.rules = rules
        self.issues: list[Issue] = []

    def check_all(self) -> list[Issue]:
        """
        Run all format checks.

        Returns:
            List of issues found.
        """
        self.issues = []

        # Run all checkers
        self.check_page_margins()
        self.check_fonts()
        self.check_font_sizes()
        self.check_line_spacing()
        self.check_paragraph_spacing()
        self.check_heading_styles()
        self.check_page_numbers()
        self.check_table_of_contents()
        self.check_references()
        self.check_indents()

        # Sort issues by severity
        severity_order = {Severity.ERROR: 0, Severity.WARNING: 1, Severity.INFO: 2}
        self.issues.sort(key=lambda x: severity_order[x.severity])

        return self.issues

    # ─── Page Margin Checks ───

    def check_page_margins(self) -> None:
        """Check page margins against rules."""
        if "page_margin" not in self.rules:
            return

        margin_rules = self.rules["page_margin"]

        for section in self.document_info.sections:
            # Check each margin
            self._check_single_margin(section, "top", margin_rules)
            self._check_single_margin(section, "bottom", margin_rules)
            self._check_single_margin(section, "left", margin_rules)
            self._check_single_margin(section, "right", margin_rules)

    def _check_single_margin(
        self, section: SectionInfo, side: str, margin_rules: dict
    ) -> None:
        """Check a single margin against the rule."""
        if side not in margin_rules:
            return

        expected = self._parse_margin_value(margin_rules[side])
        if expected is None:
            return

        current = getattr(section, f"{side}_margin_cm")

        if abs(current - expected) > self.MARGIN_TOLERANCE_CM:
            self.issues.append(Issue(
                severity=Severity.ERROR,
                category=Category.MARGIN,
                location={"section": section.index},
                rule_id=f"margin.{side}",
                current_value=f"{current:.2f}cm",
                expected_value=f"{expected:.2f}cm",
                suggestion=f"将{self._get_margin_side_cn(side)}从 {current:.2f}cm 改为 {expected:.2f}cm",
                fixable=True,
            ))

    # ─── Font Checks ───

    def check_fonts(self) -> None:
        """Check fonts against rules."""
        if "font" not in self.rules:
            return

        font_rules = self.rules["font"]
        cn_body_font = font_rules.get("cn_body")
        en_body_font = font_rules.get("en_body")

        for para in self.document_info.paragraphs:
            # Skip headings and empty paragraphs
            if para.element_type == ElementType.HEADING:
                continue
            if not para.text.strip():
                continue

            # Check Chinese font
            if cn_body_font and para.font_info.name_east_asia:
                if para.font_info.name_east_asia != cn_body_font:
                    self.issues.append(Issue(
                        severity=Severity.WARNING,
                        category=Category.FONT,
                        location={"paragraph": para.index, "page": para.page_number},
                        rule_id="font.cn_body",
                        current_value=para.font_info.name_east_asia,
                        expected_value=cn_body_font,
                        suggestion=f"将中文字体从 {para.font_info.name_east_asia} 改为 {cn_body_font}",
                        fixable=True,
                    ))

            # Check English font
            if en_body_font and para.font_info.name_ascii:
                if para.font_info.name_ascii != en_body_font:
                    self.issues.append(Issue(
                        severity=Severity.WARNING,
                        category=Category.FONT,
                        location={"paragraph": para.index, "page": para.page_number},
                        rule_id="font.en_body",
                        current_value=para.font_info.name_ascii,
                        expected_value=en_body_font,
                        suggestion=f"将英文字体从 {para.font_info.name_ascii} 改为 {en_body_font}",
                        fixable=True,
                    ))

    def check_font_sizes(self) -> None:
        """Check font sizes against rules."""
        if "font_size" not in self.rules:
            return

        size_rules = self.rules["font_size"]
        body_size = size_rules.get("body")

        if not body_size:
            return

        expected_size = self._parse_font_size(body_size)

        for para in self.document_info.paragraphs:
            # Skip headings
            if para.element_type == ElementType.HEADING:
                # Check heading font sizes separately
                self._check_heading_font_size(para, size_rules)
                continue

            # Skip empty paragraphs
            if not para.text.strip():
                continue

            if para.font_info.size_pt and expected_size:
                if abs(para.font_info.size_pt - expected_size) > self.FONT_SIZE_TOLERANCE_PT:
                    self.issues.append(Issue(
                        severity=Severity.ERROR,
                        category=Category.FONT_SIZE,
                        location={"paragraph": para.index, "page": para.page_number},
                        rule_id="font_size.body",
                        current_value=f"{para.font_info.size_pt:.1f}pt",
                        expected_value=f"{expected_size:.1f}pt",
                        suggestion=f"将字号从 {para.font_info.size_pt:.1f}pt 改为 {expected_size:.1f}pt",
                        fixable=True,
                    ))

    def _check_heading_font_size(
        self, para: ParagraphInfo, size_rules: dict
    ) -> None:
        """Check heading font size against rules."""
        if para.heading_level is None:
            return

        heading_key = f"heading{para.heading_level}"
        expected_size = size_rules.get(heading_key)

        if expected_size and para.font_info.size_pt:
            expected_pt = self._parse_font_size(expected_size)
            if expected_pt and abs(para.font_info.size_pt - expected_pt) > self.FONT_SIZE_TOLERANCE_PT:
                self.issues.append(Issue(
                    severity=Severity.WARNING,
                    category=Category.FONT_SIZE,
                    location={"paragraph": para.index, "page": para.page_number},
                    rule_id=f"font_size.{heading_key}",
                    current_value=f"{para.font_info.size_pt:.1f}pt",
                    expected_value=f"{expected_pt:.1f}pt",
                    suggestion=f"将标题{para.heading_level}字号从 {para.font_info.size_pt:.1f}pt 改为 {expected_pt:.1f}pt",
                    fixable=True,
                ))

    # ─── Spacing Checks ───

    def check_line_spacing(self) -> None:
        """Check line spacing against rules."""
        if "line_spacing" not in self.rules:
            return

        spacing_rules = self.rules["line_spacing"]
        body_spacing = spacing_rules.get("body")

        if not body_spacing:
            return

        expected_spacing = self._parse_line_spacing(body_spacing)

        for para in self.document_info.paragraphs:
            # Skip headings and empty paragraphs
            if para.element_type == ElementType.HEADING:
                continue
            if not para.text.strip():
                continue

            if para.paragraph_format.line_spacing and expected_spacing:
                if abs(para.paragraph_format.line_spacing - expected_spacing) > self.LINE_SPACING_TOLERANCE:
                    self.issues.append(Issue(
                        severity=Severity.WARNING,
                        category=Category.LINE_SPACING,
                        location={"paragraph": para.index, "page": para.page_number},
                        rule_id="line_spacing.body",
                        current_value=f"{para.paragraph_format.line_spacing:.1f}倍",
                        expected_value=f"{expected_spacing:.1f}倍",
                        suggestion=f"将行距从 {para.paragraph_format.line_spacing:.1f}倍 改为 {expected_spacing:.1f}倍",
                        fixable=True,
                    ))

    def check_paragraph_spacing(self) -> None:
        """Check paragraph spacing against rules."""
        if "paragraph_spacing" not in self.rules:
            return

        spacing_rules = self.rules["paragraph_spacing"]
        body_spacing = spacing_rules.get("body", {})

        expected_before = self._parse_spacing_value(body_spacing.get("before"))
        expected_after = self._parse_spacing_value(body_spacing.get("after"))

        for para in self.document_info.paragraphs:
            # Skip headings
            if para.element_type == ElementType.HEADING:
                continue
            if not para.text.strip():
                continue

            # Check space before
            if expected_before is not None and para.paragraph_format.space_before_pt is not None:
                if abs(para.paragraph_format.space_before_pt - expected_before) > self.SPACING_TOLERANCE_PT:
                    self.issues.append(Issue(
                        severity=Severity.INFO,
                        category=Category.PARAGRAPH_SPACING,
                        location={"paragraph": para.index, "page": para.page_number},
                        rule_id="paragraph_spacing.before",
                        current_value=f"{para.paragraph_format.space_before_pt:.1f}pt",
                        expected_value=f"{expected_before:.1f}pt",
                        suggestion=f"将段前间距从 {para.paragraph_format.space_before_pt:.1f}pt 改为 {expected_before:.1f}pt",
                        fixable=True,
                    ))

            # Check space after
            if expected_after is not None and para.paragraph_format.space_after_pt is not None:
                if abs(para.paragraph_format.space_after_pt - expected_after) > self.SPACING_TOLERANCE_PT:
                    self.issues.append(Issue(
                        severity=Severity.INFO,
                        category=Category.PARAGRAPH_SPACING,
                        location={"paragraph": para.index, "page": para.page_number},
                        rule_id="paragraph_spacing.after",
                        current_value=f"{para.paragraph_format.space_after_pt:.1f}pt",
                        expected_value=f"{expected_after:.1f}pt",
                        suggestion=f"将段后间距从 {para.paragraph_format.space_after_pt:.1f}pt 改为 {expected_after:.1f}pt",
                        fixable=True,
                    ))

    # ─── Heading Checks ───

    def check_heading_styles(self) -> None:
        """Check heading styles against rules."""
        if "heading_style" not in self.rules:
            return

        heading_rules = self.rules["heading_style"]

        # Check for missing heading styles
        for para in self.document_info.paragraphs:
            if para.heading_level is None:
                continue

            heading_key = f"heading{para.heading_level}"
            if heading_key not in heading_rules:
                continue

            rule = heading_rules[heading_key]

            # Check font
            expected_font = rule.get("font")
            if expected_font and para.font_info.name_east_asia:
                if para.font_info.name_east_asia != expected_font:
                    self.issues.append(Issue(
                        severity=Severity.WARNING,
                        category=Category.HEADING,
                        location={"paragraph": para.index, "page": para.page_number},
                        rule_id=f"heading.{heading_key}.font",
                        current_value=para.font_info.name_east_asia,
                        expected_value=expected_font,
                        suggestion=f"将标题{para.heading_level}字体从 {para.font_info.name_east_asia} 改为 {expected_font}",
                        fixable=True,
                    ))

            # Check bold
            expected_bold = rule.get("bold", True)
            if para.font_info.bold != expected_bold:
                self.issues.append(Issue(
                    severity=Severity.INFO,
                    category=Category.HEADING,
                    location={"paragraph": para.index, "page": para.page_number},
                    rule_id=f"heading.{heading_key}.bold",
                    current_value="加粗" if para.font_info.bold else "未加粗",
                    expected_value="加粗" if expected_bold else "未加粗",
                    suggestion=f"{'为标题添加加粗' if expected_bold else '取消标题加粗'}",
                    fixable=True,
                ))

        # Check for potential headings without style
        self._detect_unstyled_headings()

    def _detect_unstyled_headings(self) -> None:
        """Detect paragraphs that look like headings but don't use heading styles."""
        for para in self.document_info.paragraphs:
            # Skip if already a heading
            if para.element_type == ElementType.HEADING:
                continue

            # Heuristics for detecting unstyled headings
            if (
                para.font_info.bold
                and para.font_info.size_pt
                and para.font_info.size_pt > 14
                and len(para.text) < 100
                and not para.text.endswith("。")
            ):
                self.issues.append(Issue(
                    severity=Severity.INFO,
                    category=Category.HEADING,
                    location={"paragraph": para.index, "page": para.page_number},
                    rule_id="heading.unstyled",
                    current_value="未使用标题样式",
                    expected_value="使用 Heading 样式",
                    suggestion=f"段落 \"{para.text[:30]}...\" 可能是标题，建议应用相应的 Heading 样式",
                    fixable=False,  # Requires manual confirmation
                ))

    # ─── Page Number Checks ───

    def check_page_numbers(self) -> None:
        """Check page number settings."""
        if "page_number" not in self.rules:
            return

        page_num_rules = self.rules["page_number"]

        # Check if page numbers exist
        expected_position = page_num_rules.get("position")
        expected_format = page_num_rules.get("format")

        # Check footers for page numbers
        has_page_numbers = False
        for footer in self.document_info.footers:
            if footer.has_page_number:
                has_page_numbers = True
                break

        if not has_page_numbers and expected_position:
            self.issues.append(Issue(
                severity=Severity.WARNING,
                category=Category.PAGE_NUMBER,
                location={"section": 0},
                rule_id="page_number.existence",
                current_value="未检测到页码",
                expected_value=f"页码位置：{expected_position}",
                suggestion="添加页码到页脚",
                fixable=True,
            ))

    # ─── TOC Checks ───

    def check_table_of_contents(self) -> None:
        """Check table of contents."""
        if "toc" not in self.rules:
            return

        toc_rules = self.rules["toc"]
        require_toc = toc_rules.get("required", True)

        if require_toc and not self.document_info.toc.exists:
            self.issues.append(Issue(
                severity=Severity.WARNING,
                category=Category.TOC,
                location={},
                rule_id="toc.existence",
                current_value="未检测到目录",
                expected_value="应包含目录",
                suggestion="在文档开头添加目录",
                fixable=True,
            ))

    # ─── Reference Checks ───

    def check_references(self) -> None:
        """Check reference formatting."""
        if "references" not in self.rules:
            return

        ref_rules = self.rules["references"]
        expected_indent = ref_rules.get("indent")

        # Find reference section
        ref_start = None
        for i, para in enumerate(self.document_info.paragraphs):
            if "参考文献" in para.text or "References" in para.text:
                ref_start = i
                break

        if ref_start is None:
            return

        # Check reference paragraphs
        for para in self.document_info.paragraphs[ref_start + 1:]:
            # Stop at next section
            if para.element_type == ElementType.HEADING and para.heading_level == 1:
                break

            if not para.text.strip():
                continue

            # Check for hanging indent
            if expected_indent == "hanging" or expected_indent == "悬挂缩进":
                if para.paragraph_format.hanging_indent_pt is None or para.paragraph_format.hanging_indent_pt <= 0:
                    if para.paragraph_format.first_line_indent_pt is None or para.paragraph_format.first_line_indent_pt >= 0:
                        self.issues.append(Issue(
                            severity=Severity.WARNING,
                            category=Category.REFERENCE,
                            location={"paragraph": para.index, "page": para.page_number},
                            rule_id="references.indent",
                            current_value="无悬挂缩进",
                            expected_value="悬挂缩进",
                            suggestion="为参考文献添加悬挂缩进",
                            fixable=True,
                        ))

    # ─── Indent Checks ───

    def check_indents(self) -> None:
        """Check paragraph indentation."""
        if "indent" not in self.rules:
            return

        indent_rules = self.rules["indent"]
        first_line_indent = indent_rules.get("first_line")

        if not first_line_indent:
            return

        expected_indent = self._parse_indent_value(first_line_indent)

        for para in self.document_info.paragraphs:
            # Skip headings and empty paragraphs
            if para.element_type == ElementType.HEADING:
                continue
            if not para.text.strip():
                continue

            # Skip references (handled separately)
            if "参考文献" in para.text:
                break

            if expected_indent is not None:
                current = para.paragraph_format.first_line_indent_pt or 0
                if abs(current - expected_indent) > self.SPACING_TOLERANCE_PT:
                    self.issues.append(Issue(
                        severity=Severity.INFO,
                        category=Category.INDENT,
                        location={"paragraph": para.index, "page": para.page_number},
                        rule_id="indent.first_line",
                        current_value=f"{current:.1f}pt" if current else "无首行缩进",
                        expected_value=f"{expected_indent:.1f}pt",
                        suggestion=f"将首行缩进设置为 {expected_indent:.1f}pt",
                        fixable=True,
                    ))

    # ─── Utility Methods ───

    @staticmethod
    def _get_margin_side_cn(side: str) -> str:
        """Get Chinese name for margin side."""
        return {
            "top": "上边距",
            "bottom": "下边距",
            "left": "左边距",
            "right": "右边距",
        }.get(side, side)

    @staticmethod
    def _parse_margin_value(value: str) -> Optional[float]:
        """Parse margin value string to cm."""
        if not value:
            return None
        value = str(value).strip().lower()
        try:
            if value.endswith("cm"):
                return float(value[:-2])
            elif value.endswith("mm"):
                return float(value[:-2]) / 10
            elif value.endswith("in") or value.endswith("inch"):
                return float(value.replace("inch", "").replace("in", "")) * 2.54
            else:
                return float(value)
        except ValueError:
            return None

    @staticmethod
    def _parse_font_size(value: str) -> Optional[float]:
        """Parse font size string to pt."""
        if not value:
            return None
        value = str(value).strip().lower()
        try:
            if value.endswith("pt"):
                return float(value[:-2])
            elif value.endswith("px"):
                return float(value[:-2]) * 0.75
            elif value.endswith("cm"):
                return float(value[:-2]) / 0.0352778
            else:
                return float(value)
        except ValueError:
            return None

    @staticmethod
    def _parse_line_spacing(value: str) -> Optional[float]:
        """Parse line spacing string."""
        if not value:
            return None
        value = str(value).strip()
        try:
            if "倍" in value:
                return float(value.replace("倍", "").strip())
            elif value == "单倍" or value == "single":
                return 1.0
            elif value == "1.5倍" or value == "1.5 lines":
                return 1.5
            elif value == "双倍" or value == "double":
                return 2.0
            else:
                return float(value)
        except ValueError:
            return None

    @staticmethod
    def _parse_spacing_value(value: str) -> Optional[float]:
        """Parse spacing value string to pt."""
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
    def _parse_indent_value(value: str) -> Optional[float]:
        """Parse indent value string to pt."""
        if not value:
            return None
        value = str(value).strip().lower()
        try:
            if value.endswith("pt"):
                return float(value[:-2])
            elif value.endswith("cm"):
                return float(value[:-2]) / 0.0352778
            elif "字符" in value:
                # Approximate: 1 Chinese character ≈ 12pt
                chars = float(value.replace("字符", "").strip())
                return chars * 12
            else:
                return float(value)
        except ValueError:
            return None
