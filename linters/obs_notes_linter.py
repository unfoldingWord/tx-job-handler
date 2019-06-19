import os
import re
from linters.markdown_linter import MarkdownLinter
from linters.obs_data import obs_data
from general_tools.file_utils import read_file
from global_settings.global_settings import GlobalSettings


class ObsNotesLinter(MarkdownLinter):

    def lint(self):
        """
        Checks for issues with OBS notes: OBS-tq and OBS-tn

        Use self.log.warning("message") to log any issues.
        self.source_dir is the directory of .md files
        :return bool:
        """
        #GlobalSettings.logger.debug("ObsNotesLinter.lint()")

        # chapter check
        project_dir = os.path.join(self.source_dir, self.rc.project().path)
        GlobalSettings.logger.debug(f"project_dir1 = {project_dir}")
        if not os.path.isdir(project_dir):
            project_dir = self.source_dir
            GlobalSettings.logger.debug(f"project_dir2 = {project_dir}")
        GlobalSettings.logger.debug(f"project_dir contains {os.listdir(project_dir)}")

        # reference_re = re.compile(r'^_.*_ *$', re.M | re.U)
        # for story_number in range(1, 50+1):
        #     story_number_string = str(story_number).zfill(2)
        #     story_folder_path = os.path.join(project_dir, f'{story_number_string}/')

        #     if not os.path.isdir(story_folder_path):
        #         self.log.warning(f"Story {story_number_string} does not exist!")
        #         continue

        #     file_list = os.listdir(story_folder_path)
        #     if not file_list:
        #         self.log.warning(f"Story {story_number_string} folder is empty!")
        #         continue

        return super(ObsNotesLinter, self).lint()  # Runs the markdown linter
