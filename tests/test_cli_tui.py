"""
CLI TUI 交互式模式测试

Author: ModuleMirror
"""

from click.testing import CliRunner

from gh_similarity_detector.cli.main import main


class TestTrogonIntegration:
    def test_tui_command_exists(self):
        runner = CliRunner()
        result = runner.invoke(main, ["--help"])
        assert result.exit_code == 0
        assert "tui" in result.output

    def test_app_command_exists(self):
        runner = CliRunner()
        result = runner.invoke(main, ["--help"])
        assert result.exit_code == 0
        assert "app" in result.output

    def test_app_command_help(self):
        runner = CliRunner()
        result = runner.invoke(main, ["app", "--help"])
        assert result.exit_code == 0
        assert "TUI" in result.output or "interactive" in result.output.lower()


class TestTUIAppImport:
    def test_tui_app_module_importable(self):
        from gh_similarity_detector.cli.tui_app import ModuleMirrorTUI, DashboardScreen

        assert ModuleMirrorTUI is not None
        assert DashboardScreen is not None

    def test_tui_app_has_css(self):
        from gh_similarity_detector.cli.tui_app import ModuleMirrorTUI

        assert ModuleMirrorTUI.CSS is not None
        assert len(ModuleMirrorTUI.CSS) > 0

    def test_tui_app_title(self):
        from gh_similarity_detector.cli.tui_app import ModuleMirrorTUI

        assert ModuleMirrorTUI.TITLE == "ModuleMirror"

    def test_dashboard_screen_bindings(self):
        from gh_similarity_detector.cli.tui_app import DashboardScreen

        binding_keys = [b.key for b in DashboardScreen.BINDINGS]
        assert "q" in binding_keys
        assert "w" in binding_keys
        assert "r" in binding_keys
        assert "b" in binding_keys

    def test_core_available_flag(self):
        from gh_similarity_detector.cli.tui_app import _CORE_AVAILABLE

        assert isinstance(_CORE_AVAILABLE, bool)


class TestCLICommandsComplete:
    def test_all_commands_in_help(self):
        runner = CliRunner()
        result = runner.invoke(main, ["--help"])
        assert result.exit_code == 0
        for cmd in ["detect", "plagiarism", "search", "ncd", "diff", "browse", "dashboard", "app"]:
            assert cmd in result.output

    def test_version_is_2_0_0(self):
        runner = CliRunner()
        result = runner.invoke(main, ["--version"])
        assert result.exit_code == 0
        assert "2.0.0" in result.output
