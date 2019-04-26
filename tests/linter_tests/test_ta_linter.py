import os
import tempfile
import shutil
import mock
from tests.linter_tests.linter_unittest import LinterTestCase
from linters.ta_linter import TaLinter


class TestTaLinter(LinterTestCase):

    resources_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'resources')

    def setUp(self):
        """Runs before each test."""
        self.temp_dir = tempfile.mkdtemp(prefix='tX_test_ta_')

    def tearDown(self):
        """Runs after each test."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    @mock.patch('linters.markdown_linter.MarkdownLinter.invoke_markdown_linter')
    def test_lint(self, mock_invoke_markdown_linter):
        mock_invoke_markdown_linter.return_value = {}  # Don't care about markdown linting here, just specific ta linting
        expected_warnings = False
        zip_file = os.path.join(self.resources_dir, 'ta_linter', 'en_ta.zip')
        linter = TaLinter(repo_subject='Translation_Academy', source_file=zip_file)
        linter.run()
        self.verify_results(expected_warnings, linter)

    def verify_results(self, expected_warnings, linter):
        self.assertEqual(len(linter.log.warnings) > 0, expected_warnings)
