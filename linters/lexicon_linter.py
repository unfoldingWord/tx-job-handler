import os
import re
from linters.markdown_linter import MarkdownLinter
from general_tools.file_utils import read_file
from global_settings.global_settings import GlobalSettings


class LexiconLinter(MarkdownLinter):

    def lint(self):
        """
        Checks for issues with OBS

        Use self.log.warning("message") to log any issues.
        self.source_dir is the directory of .md files
        :return bool:
        """
        GlobalSettings.logger.debug("LexiconLinter.lint()…")

        project_dir = os.path.join(self.source_dir, self.rc.project().path)
        GlobalSettings.logger.debug(f"project_dir = {project_dir}")

        # Check front and back matter
        for book_end in ['front', 'back']:
            filename = os.path.join(project_dir, book_end, 'intro.md')
            if not os.path.isfile(filename):
                filename = os.path.join(project_dir, '{0}.md'.format(book_end))

            lines = {
                'front': 'The licensor cannot revoke',
                'back':  'We want to make this visual'
            }

            if not os.path.isfile(filename):
                self.log.warning(f"{book_end}.md does not exist!")
                continue

            if self.rc.resource.language.identifier != 'en':
                end_content = read_file(filename)
                if lines[book_end] in end_content:
                    self.log.warning(f"Story {book_end} matter is not translated!")

        return super(LexiconLinter, self).lint()  # Runs the markdown linter
