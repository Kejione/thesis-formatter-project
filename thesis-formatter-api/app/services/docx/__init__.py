"""
Document processing services.

This module provides comprehensive document processing capabilities:
- Parser: Extract formatting information from DOCX files
- Checker: Check document formatting against rules
- Fixer: Apply fixes to formatting issues
- Generator: Generate fixed documents and reports
- Processor: Main entry point that orchestrates all operations
"""

from app.services.docx.parser import (
    DocxParser,
    DocumentInfo,
    ParagraphInfo,
    SectionInfo,
    HeaderFooterInfo,
    TableInfo,
    ImageInfo,
    TOCInfo,
    FontInfo,
    ParagraphFormat,
    ElementType,
)
from app.services.docx.checker import (
    FormatChecker,
    Issue,
    Severity,
    Category,
)
from app.services.docx.fixer import (
    FormatFixer,
    ChangeRecord,
)
from app.services.docx.generator import DocxGenerator
from app.services.docx.processor import (
    DocumentProcessor,
    ProcessResult,
    process_document,
)

__all__ = [
    # Parser
    "DocxParser",
    "DocumentInfo",
    "ParagraphInfo",
    "SectionInfo",
    "HeaderFooterInfo",
    "TableInfo",
    "ImageInfo",
    "TOCInfo",
    "FontInfo",
    "ParagraphFormat",
    "ElementType",
    # Checker
    "FormatChecker",
    "Issue",
    "Severity",
    "Category",
    # Fixer
    "FormatFixer",
    "ChangeRecord",
    # Generator
    "DocxGenerator",
    # Processor
    "DocumentProcessor",
    "ProcessResult",
    "process_document",
]
