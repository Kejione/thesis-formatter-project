"""
Document processing service - Main entry point.

Integrates all document processing modules: Parser, Checker, Fixer, Generator.
"""

from dataclasses import dataclass
from io import BytesIO
from typing import Optional
import os
import tempfile

from docx import Document

try:
    from app.services.docx.parser import DocxParser, DocumentInfo
    from app.services.docx.checker import FormatChecker, Issue
    from app.services.docx.fixer import FormatFixer, ChangeRecord
    from app.services.docx.generator import DocxGenerator
except ImportError:
    # Allow standalone import for testing
    import sys
    import os
    import importlib.util
    
    def load_module_from_file(module_name, file_name):
        file_path = os.path.join(os.path.dirname(__file__), file_name)
        spec = importlib.util.spec_from_file_location(module_name, file_path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
        return module
    
    # Load modules directly
    parser_module = load_module_from_file("parser_module", 'parser.py')
    checker_module = load_module_from_file("checker_module", 'checker.py')
    fixer_module = load_module_from_file("fixer_module", 'fixer.py')
    generator_module = load_module_from_file("generator_module", 'generator.py')
    
    DocxParser = parser_module.DocxParser
    DocumentInfo = parser_module.DocumentInfo
    FormatChecker = checker_module.FormatChecker
    Issue = checker_module.Issue
    FormatFixer = fixer_module.FormatFixer
    ChangeRecord = fixer_module.ChangeRecord
    DocxGenerator = generator_module.DocxGenerator


@dataclass
class ProcessResult:
    """Result of document processing."""

    # Document info
    document_info: DocumentInfo

    # Issues found
    issues: list[Issue]

    # Changes made (after fixing)
    changes: list[ChangeRecord]

    # Fixed document bytes
    fixed_document_bytes: Optional[bytes] = None

    # Generated reports
    change_log_markdown: Optional[str] = None
    report_markdown: Optional[str] = None


class DocumentProcessor:
    """
    Main document processing service.

    Orchestrates parsing, checking, fixing, and generation.
    """

    def __init__(self, rules: dict):
        """
        Initialize processor.

        Args:
            rules: Format rules to check against.
        """
        self.rules = rules

    def process(
        self,
        document_path: str,
        fix: bool = True,
        generate_reports: bool = True,
    ) -> ProcessResult:
        """
        Process a document: parse, check, fix, and generate reports.

        Args:
            document_path: Path to the DOCX file.
            fix: Whether to apply fixes.
            generate_reports: Whether to generate markdown reports.

        Returns:
            ProcessResult containing all processing outputs.
        """
        # Step 1: Parse document
        parser = DocxParser(document_path)
        document_info = parser.parse()

        # Step 2: Check formatting
        checker = FormatChecker(document_info, self.rules)
        issues = checker.check_all()

        # Step 3: Fix issues (if requested)
        changes = []
        fixed_document_bytes = None

        if fix and issues:
            # Load document for modification
            document = Document(document_path)

            # Apply fixes
            fixer = FormatFixer(document, self.rules)
            fixable_issues = [i for i in issues if i.fixable]
            changes = fixer.fix_all(fixable_issues)

            # Generate fixed document bytes
            buffer = BytesIO()
            document.save(buffer)
            buffer.seek(0)
            fixed_document_bytes = buffer.getvalue()

        # Step 4: Generate reports (if requested)
        change_log_markdown = None
        report_markdown = None

        if generate_reports:
            generator = DocxGenerator(
                Document(document_path),  # Load fresh copy for generator
                os.path.basename(document_path),
            )

            # Document info dict for reports
            doc_info_dict = {
                "标题": document_info.title,
                "页数": document_info.page_count,
                "字数": document_info.word_count,
                "字符数": document_info.char_count,
                "作者": document_info.author,
            }

            # Generate change log
            if changes:
                change_log_markdown = generator.generate_change_log_markdown(
                    changes, doc_info_dict
                )

            # Generate full report
            report_markdown = generator.generate_report_markdown(
                issues, changes, doc_info_dict, self.rules
            )

        return ProcessResult(
            document_info=document_info,
            issues=issues,
            changes=changes,
            fixed_document_bytes=fixed_document_bytes,
            change_log_markdown=change_log_markdown,
            report_markdown=report_markdown,
        )

    def check_only(self, document_path: str) -> tuple[DocumentInfo, list[Issue]]:
        """
        Only check document without fixing.

        Args:
            document_path: Path to the DOCX file.

        Returns:
            Tuple of (DocumentInfo, list of Issues).
        """
        parser = DocxParser(document_path)
        document_info = parser.parse()

        checker = FormatChecker(document_info, self.rules)
        issues = checker.check_all()

        return document_info, issues

    def fix_only(
        self, document_path: str, issue_ids: Optional[list[str]] = None
    ) -> tuple[list[ChangeRecord], bytes]:
        """
        Apply fixes to document.

        Args:
            document_path: Path to the DOCX file.
            issue_ids: Optional list of specific issue IDs to fix.
                      If None, fixes all fixable issues.

        Returns:
            Tuple of (list of ChangeRecords, fixed document bytes).
        """
        # First, check the document
        parser = DocxParser(document_path)
        document_info = parser.parse()

        checker = FormatChecker(document_info, self.rules)
        issues = checker.check_all()

        # Filter issues if specific IDs provided
        if issue_ids:
            issues = [i for i in issues if i.rule_id in issue_ids]

        # Load document for modification
        document = Document(document_path)

        # Apply fixes
        fixer = FormatFixer(document, self.rules)
        fixable_issues = [i for i in issues if i.fixable]
        changes = fixer.fix_all(fixable_issues)

        # Get fixed document bytes
        buffer = BytesIO()
        document.save(buffer)
        buffer.seek(0)

        return changes, buffer.getvalue()


def process_document(
    document_path: str,
    rules: dict,
    fix: bool = True,
    generate_reports: bool = True,
) -> ProcessResult:
    """
    Convenience function to process a document.

    Args:
        document_path: Path to the DOCX file.
        rules: Format rules to check against.
        fix: Whether to apply fixes.
        generate_reports: Whether to generate markdown reports.

    Returns:
        ProcessResult containing all processing outputs.
    """
    processor = DocumentProcessor(rules)
    return processor.process(document_path, fix, generate_reports)
