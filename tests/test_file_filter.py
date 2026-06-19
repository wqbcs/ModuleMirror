from gh_similarity_detector.core.project.file_filter import FileFilter


class TestFileFilter:
    def test_include_python_file(self):
        f = FileFilter(languages=["python"])
        assert f.should_include("src/main.py") is True

    def test_exclude_node_modules(self):
        f = FileFilter(languages=["python"])
        assert f.should_include("node_modules/package/index.js") is False

    def test_exclude_venv(self):
        f = FileFilter(languages=["python"])
        assert f.should_include("venv/lib/site-packages/foo.py") is False

    def test_exclude_min_js(self):
        f = FileFilter(languages=["javascript"])
        assert f.should_include("app/bundle.min.js") is False

    def test_exclude_non_code(self):
        f = FileFilter(languages=["python"])
        assert f.should_include("README.md") is False
        assert f.should_include("config.json") is False

    def test_include_typescript(self):
        f = FileFilter(languages=["typescript"])
        assert f.should_include("src/app.tsx") is True

    def test_get_language_python(self):
        f = FileFilter(languages=["python"])
        assert f.get_language("main.py") == "python"

    def test_get_language_unknown(self):
        f = FileFilter(languages=["python"])
        assert f.get_language("data.csv") is None

    def test_is_code_file(self):
        f = FileFilter(languages=["python", "java"])
        assert f.is_code_file("App.java") is True
        assert f.is_code_file("style.css") is False

    def test_custom_exclude_dirs(self):
        f = FileFilter(languages=["python"], exclude_dirs={"custom_excluded"})
        assert f.should_include("custom_excluded/foo.py") is False
        assert f.should_include("src/main.py") is True
