"""
i18n 国际化测试

Author: ModuleMirror
"""

from gh_similarity_detector.infrastructure.i18n import (
    I18n, set_locale, get_locale, t, register_messages,
)


class TestI18n:
    def setup_method(self):
        I18n.reset()

    def test_default_locale_is_zh(self):
        i18n = I18n.get_instance()
        assert i18n.locale == "zh"

    def test_set_locale(self):
        i18n = I18n.get_instance()
        i18n.locale = "en"
        assert i18n.locale == "en"

    def test_set_unsupported_locale(self):
        i18n = I18n.get_instance()
        try:
            i18n.locale = "fr"
            assert False, "Should raise ValueError"
        except ValueError as e:
            assert "Unsupported locale" in str(e)

    def test_supported_locales(self):
        i18n = I18n.get_instance()
        assert "zh" in i18n.supported_locales
        assert "en" in i18n.supported_locales

    def test_translate_zh(self):
        i18n = I18n.get_instance()
        msg = i18n.translate("error.db.connection", detail="timeout")
        assert "数据库连接失败" in msg
        assert "timeout" in msg

    def test_translate_en(self):
        i18n = I18n.get_instance()
        i18n.locale = "en"
        msg = i18n.translate("error.db.connection", detail="timeout")
        assert "Database connection failed" in msg
        assert "timeout" in msg

    def test_translate_with_kwargs(self):
        i18n = I18n.get_instance()
        msg = i18n.translate("error.detect.no_fingerprints", module="foo.py")
        assert "foo.py" in msg

    def test_translate_missing_key_returns_key(self):
        i18n = I18n.get_instance()
        msg = i18n.translate("nonexistent.key.xyz")
        assert msg == "nonexistent.key.xyz"

    def test_translate_fallback_to_default(self):
        i18n = I18n.get_instance()
        i18n.locale = "en"
        i18n.register_messages("zh", {"test.only.zh": "仅中文"})
        msg = i18n.translate("test.only.zh")
        assert msg == "仅中文"

    def test_translate_partial_kwargs(self):
        i18n = I18n.get_instance()
        msg = i18n.translate("error.db.migration", from_ver="1", to_ver="2")
        assert "1" in msg
        assert "2" in msg

    def test_register_messages_new_locale(self):
        i18n = I18n.get_instance()
        i18n.register_messages("ja", {"hello": "こんにちは"})
        i18n._messages["ja"] = {"hello": "こんにちは"}
        assert "hello" in i18n._messages.get("ja", {})

    def test_register_messages_extend(self):
        i18n = I18n.get_instance()
        i18n.register_messages("zh", {"custom.key": "自定义消息"})
        msg = i18n.translate("custom.key")
        assert msg == "自定义消息"

    def test_get_all_keys(self):
        i18n = I18n.get_instance()
        keys = i18n.get_all_keys()
        assert len(keys) > 0
        assert "error.db.connection" in keys

    def test_has_key(self):
        i18n = I18n.get_instance()
        assert i18n.has_key("error.db.connection") is True
        assert i18n.has_key("nonexistent.xyz") is False

    def test_singleton(self):
        i1 = I18n.get_instance()
        i2 = I18n.get_instance()
        assert i1 is i2

    def test_reset(self):
        i1 = I18n.get_instance()
        I18n.reset()
        i2 = I18n.get_instance()
        assert i1 is not i2


class TestModuleFunctions:
    def setup_method(self):
        I18n.reset()

    def test_set_locale_function(self):
        set_locale("en")
        assert get_locale() == "en"

    def test_t_function_zh(self):
        msg = t("error.auth.token_expired")
        assert "过期" in msg

    def test_t_function_en(self):
        set_locale("en")
        msg = t("error.auth.token_expired")
        assert "expired" in msg.lower()

    def test_t_with_kwargs(self):
        msg = t("error.io.file_not_found", path="/tmp/foo.py")
        assert "/tmp/foo.py" in msg

    def test_register_messages_function(self):
        register_messages("zh", {"test.fn": "函数注册"})
        msg = t("test.fn")
        assert msg == "函数注册"
