import os
import re

from app_settings.app_settings import AppSettings
from general_tools.file_utils import read_file
from linters.markdown_linter import MarkdownLinter
from linters.obs_data import obs_data


class ObsLinter(MarkdownLinter):

    def lint(self) -> bool:
        """
        Checks for issues with OBS

        Use self.log.warning("message") to log any issues.
        self.source_dir is the directory of .md files
        :return bool:
        """
        #AppSettings.logger.debug("ObsLinter.lint()")

        # chapter check
        project_dir = os.path.join(self.source_dir, self.rc.project().path)
        AppSettings.logger.debug(f"project_dir1 = {project_dir}")
        if not os.path.isdir(project_dir):
            project_dir = self.source_dir
            AppSettings.logger.debug(f"project_dir2 = {project_dir}")
        AppSettings.logger.debug(f"project_dir contains {os.listdir(project_dir)}")

        reference_re = re.compile(r'^_.*_ *$', re.M | re.U)
        for chapter in range(1, 51):
            chapter_number = str(chapter).zfill(2)
            filename = os.path.join(project_dir, chapter_number + '.md')

            if not os.path.isfile(filename):
                self.log.warning(f"Chapter {chapter_number} does not exist.")
                continue

            chapter_md = read_file(filename)
            is_title = chapter_md.find('# ')

            # Find chapter headings
            if is_title < 0:
                self.log.warning(f"Chapter {chapter_number} does not have a title.")

            # Identify missing frames
            expected_frame_count = obs_data['chapters'][str(chapter).zfill(2)]['frames']

            for frame_idx in range(1, expected_frame_count):
                frame_index = str(frame_idx).zfill(2)
                pattern_strict = '-{0}-{1}.jpg)\n'.format(chapter_number, frame_index)
                strict_find_result = chapter_md.find(pattern_strict)
                if strict_find_result < 0: # not found
                    pattern_loose = '-{0}-{1}.'.format(chapter_number, frame_index)
                    if chapter_md.find(pattern_loose) < 0:
                        self.log.warning(f"Missing frame: {chapter_number}-{frame_index}")
                    else: # failed the strict one, but found the loose one
                        self.log.warning(f"Unexpected picture link formatting: {chapter_number}-{frame_index}")

            # look for verse reference
            if not reference_re.search(chapter_md):
                self.log.warning(f"Bible reference not found at end of chapter {chapter_number}!")

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
                self.log.warning(f"{book_end}.md does not exist.")
                continue

            if self.rc.resource.language.identifier != 'en':
                end_content = read_file(filename)
                if lines[book_end] in end_content:
                    self.log.warning(f"Story {book_end} matter is not translated.")

        return super(ObsLinter, self).lint()  # Runs the markdown linter
