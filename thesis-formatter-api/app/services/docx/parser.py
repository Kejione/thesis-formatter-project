"""
Document processing service - Parser.

Parses DOCX files and extracts comprehensive formatting information.
Supports: page margins, fonts, line spacing, headings, headers/footers,
page numbers, table of contents, references, tables, images, and formulas.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
import re

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn


class ElementType(Enum):
    """Type of document element."""
    PARAGRAPH = "paragraph"
    HEADING = "heading"
    TABLE = "table"
    IMAGE = "image"
    FORMULA = "formula"
    PAGE_BREAK = "page_break"
    TOC = "toc"  # Table of contents


@dataclass
class FontInfo:
    """Font information for a text run."""
    name_ascii: Optional[str] = None
    name_east_asia: Optional[str] = None
    name_h_ansi: Optional[str] = None
    size_pt: Optional[float] = None
    bold: bool = False
    italic: bool = False
    underline: bool = False
    color: Optional[str] = None


@dataclass
class ParagraphFormat:
    """Paragraph formatting information."""
    alignment: Optional[str] = None  # left, center, right, justify
    line_spacing: Optional[float] = None  # Multiplier or exact value
    line_spacing_rule: Optional[str] = None  # single, 1.5, double, exact, multiple
    space_before_pt: Optional[float] = None
    space_after_pt: Optional[float] = None
    first_line_indent_pt: Optional[float] = None
    left_indent_pt: Optional[float] = None
    hanging_indent_pt: Optional[float] = None


@dataclass
class ParagraphInfo:
    """Information about a paragraph."""
    index: int
    text: str
    element_type: ElementType = ElementType.PARAGRAPH
    style_name: Optional[str] = None
    heading_level: Optional[int] = None  # 1-6 for headings, None for regular paragraphs
    font_info: FontInfo = field(default_factory=FontInfo)
    paragraph_format: ParagraphFormat = field(default_factory=ParagraphFormat)
    page_number: Optional[int] = None  # Approximate page number


@dataclass
class HeaderFooterInfo:
    """Information about header or footer."""
    type: str  # "header" or "footer"
    section_index: int
    text: str
    has_page_number: bool = False
    page_number_format: Optional[str] = None  # "arabic", "roman_upper", "roman_lower"
    alignment: Optional[str] = None


@dataclass
class SectionInfo:
    """Information about a document section."""
    index: int
    # Page setup
    page_width_cm: float = 21.0
    page_height_cm: float = 29.7
    top_margin_cm: float = 2.54
    bottom_margin_cm: float = 2.54
    left_margin_cm: float = 3.17
    right_margin_cm: float = 3.17
    # Header/footer
    header_distance_cm: Optional[float] = None
    footer_distance_cm: Optional[float] = None
    different_first_page: bool = False
    odd_even_pages_different: bool = False
    # Page number
    page_number_start: Optional[int] = None
    page_number_format: Optional[str] = None  # "arabic", "roman_upper", "roman_lower"


@dataclass
class TableInfo:
    """Information about a table."""
    index: int
    row_count: int
    column_count: int
    caption: Optional[str] = None
    page_number: Optional[int] = None


@dataclass
class ImageInfo:
    """Information about an image."""
    index: int
    width_cm: Optional[float] = None
    height_cm: Optional[float] = None
    caption: Optional[str] = None
    page_number: Optional[int] = None


@dataclass
class TOCInfo:
    """Information about table of contents."""
    exists: bool = False
    heading_count: int = 0
    page_range: Optional[tuple[int, int]] = None


@dataclass
class DocumentInfo:
    """Complete document information."""
    # Sections
    sections: list[SectionInfo] = field(default_factory=list)
    # Content elements
    paragraphs: list[ParagraphInfo] = field(default_factory=list)
    tables: list[TableInfo] = field(default_factory=list)
    images: list[ImageInfo] = field(default_factory=list)
    # Headers and footers
    headers: list[HeaderFooterInfo] = field(default_factory=list)
    footers: list[HeaderFooterInfo] = field(default_factory=list)
    # Special elements
    toc: TOCInfo = field(default_factory=TOCInfo)
    # Statistics
    page_count: int = 0
    word_count: int = 0
    char_count: int = 0
    # Metadata
    title: Optional[str] = None
    author: Optional[str] = None


class DocxParser:
    """
    Parser for DOCX files.

    Extracts comprehensive formatting information without modifying content.
    """

    def __init__(self, file_path: str):
        """
        Initialize parser with file path.

        Args:
            file_path: Path to the DOCX file.
        """
        self.file_path = file_path
        self._document: Optional[Document] = None
        self._current_page = 1
        self._paragraphs_per_page = 25  # Approximate for page estimation

    def load(self) -> None:
        """Load the document."""
        self._document = Document(self.file_path)

    def parse(self) -> DocumentInfo:
        """
        Parse the document and extract all formatting information.

        Returns:
            DocumentInfo containing all extracted information.
        """
        if not self._document:
            self.load()

        # Parse all components
        sections = self._parse_sections()
        paragraphs = self._parse_paragraphs()
        tables = self._parse_tables()
        images = self._parse_images()
        headers, footers = self._parse_headers_footers()
        toc = self._detect_toc()

        # Calculate statistics
        page_count = self._estimate_page_count()
        word_count, char_count = self._count_words_and_chars()

        # Extract metadata
        title = self._extract_title()
        author = self._extract_author()

        return DocumentInfo(
            sections=sections,
            paragraphs=paragraphs,
            tables=tables,
            images=images,
            headers=headers,
            footers=footers,
            toc=toc,
            page_count=page_count,
            word_count=word_count,
            char_count=char_count,
            title=title,
            author=author,
        )

    def _parse_sections(self) -> list[SectionInfo]:
        """Parse all sections in the document."""
        sections = []
        for i, section in enumerate(self._document.sections):
            # Get page number settings
            page_num_format = self._get_page_number_format(section)
            page_num_start = self._get_page_number_start(section)

            sections.append(SectionInfo(
                index=i,
                page_width_cm=self._emu_to_cm(section.page_width) if section.page_width else 21.0,
                page_height_cm=self._emu_to_cm(section.page_height) if section.page_height else 29.7,
                top_margin_cm=self._emu_to_cm(section.top_margin) if section.top_margin else 2.54,
                bottom_margin_cm=self._emu_to_cm(section.bottom_margin) if section.bottom_margin else 2.54,
                left_margin_cm=self._emu_to_cm(section.left_margin) if section.left_margin else 3.17,
                right_margin_cm=self._emu_to_cm(section.right_margin) if section.right_margin else 3.17,
                header_distance_cm=self._emu_to_cm(section.header_distance) if section.header_distance else None,
                footer_distance_cm=self._emu_to_cm(section.footer_distance) if section.footer_distance else None,
                different_first_page=getattr(section, 'different_first_page_header_footer', False),
                odd_even_pages_different=getattr(section, 'odd_and_even_pages_header_footer', False),
                page_number_start=page_num_start,
                page_number_format=page_num_format,
            ))
        return sections

    def _parse_paragraphs(self) -> list[ParagraphInfo]:
        """Parse all paragraphs in the document."""
        paragraphs = []
        self._current_page = 1

        for i, para in enumerate(self._document.paragraphs):
            # Detect element type
            element_type, heading_level = self._detect_element_type(para)

            # Get font info from first run (if exists)
            font_info = self._extract_font_info(para)

            # Get paragraph format
            para_format = self._extract_paragraph_format(para)

            # Estimate page number
            if i > 0 and i % self._paragraphs_per_page == 0:
                self._current_page += 1

            paragraphs.append(ParagraphInfo(
                index=i,
                text=para.text[:200] + "..." if len(para.text) > 200 else para.text,
                element_type=element_type,
                style_name=para.style.name if para.style else None,
                heading_level=heading_level,
                font_info=font_info,
                paragraph_format=para_format,
                page_number=self._current_page,
            ))
        return paragraphs

    def _detect_element_type(self, para) -> tuple[ElementType, Optional[int]]:
        """Detect the type of element and heading level if applicable."""
        style_name = para.style.name if para.style else ""

        # Check for heading styles
        if style_name.startswith("Heading"):
            try:
                level = int(style_name.replace("Heading", "").strip())
                return ElementType.HEADING, level
            except ValueError:
                pass

        # Check for TOC
        if "TOC" in style_name or "toc" in style_name:
            return ElementType.TOC, None

        # Check for page break
        if para.text == "" and para._element.xml.find("w:pageBreakBefore") != -1:
            return ElementType.PAGE_BREAK, None

        return ElementType.PARAGRAPH, None

    def _extract_font_info(self, para) -> FontInfo:
        """Extract font information from a paragraph."""
        font_info = FontInfo()

        if para.runs:
            first_run = para.runs[0]
            font = first_run.font

            # Get font names
            rPr = first_run._element.rPr
            if rPr is not None:
                # ASCII font (for Latin characters)
                rFonts = rPr.find(qn('w:rFonts'))
                if rFonts is not None:
                    font_info.name_ascii = rFonts.get(qn('w:ascii'))
                    font_info.name_east_asia = rFonts.get(qn('w:eastAsia'))
                    font_info.name_h_ansi = rFonts.get(qn('w:hAnsi'))

            # Get font size
            if font.size:
                font_info.size_pt = font.size.pt

            # Get font style
            font_info.bold = font.bold or False
            font_info.italic = font.italic or False
            font_info.underline = font.underline or False

            # Get font color
            if font.color and font.color.rgb:
                font_info.color = str(font.color.rgb)

        return font_info

    def _extract_paragraph_format(self, para) -> ParagraphFormat:
        """Extract paragraph formatting information."""
        pf = para.paragraph_format
        para_format = ParagraphFormat()

        # Alignment
        if pf.alignment is not None:
            alignment_map = {
                WD_ALIGN_PARAGRAPH.LEFT: "left",
                WD_ALIGN_PARAGRAPH.CENTER: "center",
                WD_ALIGN_PARAGRAPH.RIGHT: "right",
                WD_ALIGN_PARAGRAPH.JUSTIFY: "justify",
            }
            para_format.alignment = alignment_map.get(pf.alignment)

        # Line spacing
        if pf.line_spacing is not None:
            para_format.line_spacing = pf.line_spacing
            # Determine line spacing rule
            if pf.line_spacing_rule is not None:
                rule_map = {
                    0: "single",
                    1: "1.5 lines",
                    2: "double",
                    3: "at least",
                    4: "exact",
                    5: "multiple",
                }
                para_format.line_spacing_rule = rule_map.get(pf.line_spacing_rule.value)

        # Spacing
        if pf.space_before:
            para_format.space_before_pt = pf.space_before.pt
        if pf.space_after:
            para_format.space_after_pt = pf.space_after.pt

        # Indentation
        if pf.first_line_indent:
            para_format.first_line_indent_pt = pf.first_line_indent.pt
        if pf.left_indent:
            para_format.left_indent_pt = pf.left_indent.pt
        # hanging_indent may not be available in all python-docx versions
        hanging_indent = getattr(pf, 'hanging_indent', None)
        if hanging_indent:
            para_format.hanging_indent_pt = hanging_indent.pt

        return para_format

    def _parse_tables(self) -> list[TableInfo]:
        """Parse all tables in the document."""
        tables = []
        for i, table in enumerate(self._document.tables):
            # Try to find caption (usually in the paragraph before the table)
            caption = None
            table_element = table._element
            prev_sibling = table_element.getprevious()
            if prev_sibling is not None and prev_sibling.text:
                caption = prev_sibling.text[:100]

            tables.append(TableInfo(
                index=i,
                row_count=len(table.rows),
                column_count=len(table.columns),
                caption=caption,
            ))
        return tables

    def _parse_images(self) -> list[ImageInfo]:
        """Parse all images in the document."""
        images = []
        # Find all inline shapes (images)
        for i, shape in enumerate(self._document.inline_shapes):
            # Try to find caption
            caption = None
            # This is a simplified approach; actual caption detection is more complex

            images.append(ImageInfo(
                index=i,
                width_cm=shape.width.cm if shape.width else None,
                height_cm=shape.height.cm if shape.height else None,
                caption=caption,
            ))
        return images

    def _parse_headers_footers(self) -> tuple[list[HeaderFooterInfo], list[HeaderFooterInfo]]:
        """Parse all headers and footers in the document."""
        headers = []
        footers = []

        for i, section in enumerate(self._document.sections):
            # Parse headers
            for header_type, header in [
                ("primary", section.header),
                ("first", section.first_page_header),
                ("even", section.even_page_header),
            ]:
                if header and not header.is_linked_to_previous:
                    text = "\n".join(p.text for p in header.paragraphs)
                    has_page_num, page_num_format = self._detect_page_number(text)
                    headers.append(HeaderFooterInfo(
                        type="header",
                        section_index=i,
                        text=text[:200],
                        has_page_number=has_page_num,
                        page_number_format=page_num_format,
                    ))

            # Parse footers
            for footer_type, footer in [
                ("primary", section.footer),
                ("first", section.first_page_footer),
                ("even", section.even_page_footer),
            ]:
                if footer and not footer.is_linked_to_previous:
                    text = "\n".join(p.text for p in footer.paragraphs)
                    has_page_num, page_num_format = self._detect_page_number(text)
                    footers.append(HeaderFooterInfo(
                        type="footer",
                        section_index=i,
                        text=text[:200],
                        has_page_number=has_page_num,
                        page_number_format=page_num_format,
                    ))

        return headers, footers

    def _detect_page_number(self, text: str) -> tuple[bool, Optional[str]]:
        """Detect if text contains a page number field."""
        # Check for PAGE field
        has_page_num = "PAGE" in text or "页" in text

        # Try to detect format
        page_num_format = None
        if has_page_num:
            # Default to Arabic
            page_num_format = "arabic"

        return has_page_num, page_num_format

    def _get_page_number_format(self, section) -> Optional[str]:
        """Get page number format from section."""
        # This requires accessing the XML directly
        try:
            sectPr = section._sectPr
            pgNumType = sectPr.find(qn('w:pgNumType'))
            if pgNumType is not None:
                fmt = pgNumType.get(qn('w:fmt'))
                format_map = {
                    "decimal": "arabic",
                    "upperRoman": "roman_upper",
                    "lowerRoman": "roman_lower",
                    "upperLetter": "letter_upper",
                    "lowerLetter": "letter_lower",
                }
                return format_map.get(fmt, "arabic")
        except Exception:
            pass
        return None

    def _get_page_number_start(self, section) -> Optional[int]:
        """Get page number start from section."""
        try:
            sectPr = section._sectPr
            pgNumType = sectPr.find(qn('w:pgNumType'))
            if pgNumType is not None:
                start = pgNumType.get(qn('w:start'))
                if start:
                    return int(start)
        except Exception:
            pass
        return None

    def _detect_toc(self) -> TOCInfo:
        """Detect if document has a table of contents."""
        toc_info = TOCInfo()

        for para in self._document.paragraphs:
            style_name = para.style.name if para.style else ""
            if "TOC" in style_name or "toc" in style_name:
                toc_info.exists = True
                break

        # Count headings
        heading_count = sum(1 for p in self._document.paragraphs
                          if p.style and p.style.name.startswith("Heading"))
        toc_info.heading_count = heading_count

        return toc_info

    def _estimate_page_count(self) -> int:
        """Estimate page count (approximate)."""
        # This is a rough estimate; accurate count requires rendering
        para_count = len(self._document.paragraphs)
        estimated_pages = max(1, para_count // self._paragraphs_per_page)

        # Account for page breaks
        for para in self._document.paragraphs:
            if para._element.xml.find("w:pageBreakBefore") != -1:
                estimated_pages += 1

        return estimated_pages

    def _count_words_and_chars(self) -> tuple[int, int]:
        """Count total words and characters in document."""
        total_chars = 0
        total_words = 0

        for para in self._document.paragraphs:
            text = para.text.strip()
            if text:
                total_chars += len(text)
                # Count Chinese characters and English words separately
                chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
                english_words = len(re.findall(r'[a-zA-Z]+', text))
                total_words += chinese_chars + english_words

        return total_words, total_chars

    def _extract_title(self) -> Optional[str]:
        """Extract document title from first heading or first paragraph."""
        for para in self._document.paragraphs:
            if para.style and para.style.name.startswith("Heading"):
                return para.text.strip()
            if para.text.strip():
                return para.text.strip()[:100]
        return None

    def _extract_author(self) -> Optional[str]:
        """Extract author from document properties."""
        try:
            core_props = self._document.core_properties
            return core_props.author
        except Exception:
            return None

    @staticmethod
    def _emu_to_cm(emu: int) -> float:
        """Convert EMU (English Metric Units) to centimeters."""
        if emu is None:
            return 0.0
        return emu / 914400 * 2.54

    @staticmethod
    def _pt_to_cm(pt: float) -> float:
        """Convert points to centimeters."""
        return pt * 0.0352778
