"""规则引擎：加载、合并、校验论文格式化规则。"""

from __future__ import annotations

import copy
from typing import Any

from loguru import logger


class RuleEngine:
    """管理论文格式化规则的核心引擎。

    职责：
    - 按优先级获取规则（任务快照 > 模板规则 > 默认规则）
    - 深度合并两份规则字典
    - 校验规则结构的合法性
    - 提供中国高校论文排版默认规则
    """

    # ------------------------------------------------------------------
    # 获取规则
    # ------------------------------------------------------------------

    def get_rules_for_task(self, db_session: Any, task: Any) -> dict:
        """根据任务获取适用的格式规则。

        优先级：
        1. task.rule_snapshot —— 任务创建时冻结的规则快照
        2. task.template.rule —— 任务关联模板的规则
        3. 内置默认规则

        Args:
            db_session: 数据库会话（预留，当前未直接使用）。
            task: 任务对象，需具有 ``rule_snapshot`` 和 ``template`` 属性。

        Returns:
            合并后的格式规则字典。
        """
        # 优先级 1：任务快照
        if getattr(task, "rule_snapshot", None):
            logger.debug("使用任务 rule_snapshot 作为格式规则")
            return copy.deepcopy(task.rule_snapshot)

        # 优先级 2：模板规则
        template = getattr(task, "template", None)
        if template and getattr(template, "rule", None):
            logger.debug("使用模板 rule 作为格式规则")
            base = self.get_default_rules()
            return self.merge_rules(base, template.rule)

        # 优先级 3：默认规则
        logger.info("未找到任务快照或模板规则，使用默认格式规则")
        return self.get_default_rules()

    # ------------------------------------------------------------------
    # 合并规则
    # ------------------------------------------------------------------

    @staticmethod
    def merge_rules(base_rules: dict, override_rules: dict) -> dict:
        """深度合并两份规则字典，override 中的值优先。

        对于嵌套字典会递归合并；对于非字典值，override 直接覆盖 base。

        Args:
            base_rules: 基础规则字典。
            override_rules: 覆盖规则字典。

        Returns:
            合并后的新字典（不修改原字典）。
        """
        merged = copy.deepcopy(base_rules)
        for key, value in override_rules.items():
            if (
                key in merged
                and isinstance(merged[key], dict)
                and isinstance(value, dict)
            ):
                merged[key] = RuleEngine.merge_rules(merged[key], value)
            else:
                merged[key] = copy.deepcopy(value)
        return merged

    # ------------------------------------------------------------------
    # 校验规则
    # ------------------------------------------------------------------

    def validate_rules(self, rules: dict) -> list[str]:
        """校验规则字典的结构是否合法。

        Args:
            rules: 待校验的规则字典。

        Returns:
            校验错误列表；空列表表示校验通过。
        """
        errors: list[str] = []

        if not isinstance(rules, dict):
            errors.append("规则必须是字典类型")
            return errors

        if not rules:
            errors.append("规则字典不能为空")
            return errors

        # --- page_margin ---
        page_margin = rules.get("page_margin")
        if page_margin is not None:
            if not isinstance(page_margin, dict):
                errors.append("page_margin 必须是字典类型")
            else:
                for side in ("top", "bottom", "left", "right"):
                    val = page_margin.get(side)
                    if val is not None and not isinstance(val, str):
                        errors.append(f"page_margin.{side} 必须是字符串类型")

        # --- font ---
        font = rules.get("font")
        if font is not None:
            if not isinstance(font, dict):
                errors.append("font 必须是字典类型")
            else:
                for key in ("cn_body", "en_body", "cn_title", "en_title"):
                    val = font.get(key)
                    if val is not None and not isinstance(val, str):
                        errors.append(f"font.{key} 必须是字符串类型")

        # --- font_size ---
        font_size = rules.get("font_size")
        if font_size is not None:
            if not isinstance(font_size, dict):
                errors.append("font_size 必须是字典类型")
            else:
                for key in ("body", "heading1", "heading2", "heading3"):
                    val = font_size.get(key)
                    if val is not None and not isinstance(val, str):
                        errors.append(f"font_size.{key} 必须是字符串类型")

        # --- line_spacing ---
        line_spacing = rules.get("line_spacing")
        if line_spacing is not None:
            if not isinstance(line_spacing, dict):
                errors.append("line_spacing 必须是字典类型")
            else:
                for key in ("body",):
                    val = line_spacing.get(key)
                    if val is not None and not isinstance(val, str):
                        errors.append(f"line_spacing.{key} 必须是字符串类型")

        # --- paragraph_spacing ---
        para_spacing = rules.get("paragraph_spacing")
        if para_spacing is not None:
            if not isinstance(para_spacing, dict):
                errors.append("paragraph_spacing 必须是字典类型")

        # --- heading_style ---
        heading_style = rules.get("heading_style")
        if heading_style is not None:
            if not isinstance(heading_style, dict):
                errors.append("heading_style 必须是字典类型")
            else:
                for level_key, level_val in heading_style.items():
                    if not isinstance(level_val, dict):
                        errors.append(f"heading_style.{level_key} 必须是字典类型")
                    else:
                        for prop in ("font", "size"):
                            pval = level_val.get(prop)
                            if pval is not None and not isinstance(pval, str):
                                errors.append(
                                    f"heading_style.{level_key}.{prop} 必须是字符串类型"
                                )
                        bold_val = level_val.get("bold")
                        if bold_val is not None and not isinstance(bold_val, bool):
                            errors.append(
                                f"heading_style.{level_key}.bold 必须是布尔类型"
                            )
                        center_val = level_val.get("center")
                        if center_val is not None and not isinstance(center_val, bool):
                            errors.append(
                                f"heading_style.{level_key}.center 必须是布尔类型"
                            )

        # --- page_number ---
        page_number = rules.get("page_number")
        if page_number is not None:
            if not isinstance(page_number, dict):
                errors.append("page_number 必须是字典类型")
            else:
                pos = page_number.get("position")
                if pos is not None and not isinstance(pos, str):
                    errors.append("page_number.position 必须是字符串类型")
                fmt = page_number.get("format")
                if fmt is not None and not isinstance(fmt, str):
                    errors.append("page_number.format 必须是字符串类型")

        # --- references ---
        references = rules.get("references")
        if references is not None:
            if not isinstance(references, dict):
                errors.append("references 必须是字典类型")

        # --- indent ---
        indent = rules.get("indent")
        if indent is not None:
            if not isinstance(indent, dict):
                errors.append("indent 必须是字典类型")

        # --- toc ---
        toc = rules.get("toc")
        if toc is not None:
            if not isinstance(toc, dict):
                errors.append("toc 必须是字典类型")
            else:
                required = toc.get("required")
                if required is not None and not isinstance(required, bool):
                    errors.append("toc.required 必须是布尔类型")

        if errors:
            logger.warning("规则校验发现 {} 个问题: {}", len(errors), errors)
        else:
            logger.debug("规则校验通过")

        return errors

    # ------------------------------------------------------------------
    # 默认规则
    # ------------------------------------------------------------------

    @staticmethod
    def get_default_rules() -> dict:
        """返回适用于中国高校毕业论文的默认排版规则。

        Returns:
            默认规则字典。
        """
        return {
            "page_margin": {
                "top": "2.5cm",
                "bottom": "2.5cm",
                "left": "3cm",
                "right": "2.5cm",
            },
            "font": {
                "cn_body": "宋体",
                "en_body": "Times New Roman",
                "cn_title": "黑体",
                "en_title": "Arial",
            },
            "font_size": {
                "body": "12pt",
                "heading1": "22pt",
                "heading2": "16pt",
                "heading3": "14pt",
            },
            "line_spacing": {
                "body": "1.5倍",
            },
            "paragraph_spacing": {
                "body": {"before": "0pt", "after": "0pt"},
            },
            "heading_style": {
                "heading1": {
                    "font": "黑体",
                    "size": "22pt",
                    "bold": True,
                    "center": True,
                },
            },
            "page_number": {
                "position": "footer-center",
                "format": "arabic",
            },
            "references": {
                "indent": "悬挂缩进",
                "indent_width": "2字符",
            },
            "indent": {
                "first_line": "2字符",
            },
            "toc": {
                "required": True,
            },
        }

    # ------------------------------------------------------------------
    # 快照
    # ------------------------------------------------------------------

    @staticmethod
    def rules_to_snapshot(rules: dict) -> dict:
        """将规则字典制备为可存储的快照（深拷贝）。

        Args:
            rules: 源规则字典。

        Returns:
            深拷贝后的规则字典，可安全序列化后持久化。
        """
        return copy.deepcopy(rules)


# ------------------------------------------------------------------
# 全局单例
# ------------------------------------------------------------------

_rule_engine_instance: RuleEngine | None = None


def get_rule_engine() -> RuleEngine:
    """获取全局 RuleEngine 单例。

    Returns:
        RuleEngine 实例。
    """
    global _rule_engine_instance
    if _rule_engine_instance is None:
        _rule_engine_instance = RuleEngine()
        logger.debug("RuleEngine 全局单例已创建")
    return _rule_engine_instance
