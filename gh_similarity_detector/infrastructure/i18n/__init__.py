"""
国际化 (i18n) 模块

支持 CLI/API 错误消息多语言切换。
内置中文(zh)和英文(en)，可扩展其他语言。

Author: ModuleMirror
"""

from ._i18n import I18n, set_locale, get_locale, t, register_messages

__all__ = ["I18n", "set_locale", "get_locale", "t", "register_messages"]
