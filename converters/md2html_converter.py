import os
import string
from shutil import copyfile
import logging

import markdown
import markdown2
from bs4 import BeautifulSoup

from rq_settings import prefix, debug_mode_flag
from general_tools.file_utils import write_file, get_files
from converters.converter import Converter



class Md2HtmlConverter(Converter):

    def convert(self):
        if self.repo_subject == 'obs':
            self.convert_obs()
            return True
        else:
            self.convert_markdown()
            return True


    def convert_obs(self):
        self.log.info("Converting OBS markdown files…")

        # Find the first directory that has md files.
        files = get_files(directory=self.files_dir, exclude=self.EXCLUDED_FILES)

        current_dir = os.path.dirname(os.path.realpath(__file__))
        with open(os.path.join(current_dir, 'templates', 'template.html')) as template_file:
            html_template = string.Template(template_file.read())

        found_chapters = {}

        for filename in sorted(files):
            if filename.endswith('.md'):
                # Convert files that are markdown files
                with open(filename, 'rt') as md_file:
                    md = md_file.read()
                html = markdown.markdown(md)
                html = html_template.safe_substitute(title=self.repo_subject, content=html)
                base_name = os.path.splitext(os.path.basename(filename))[0]
                found_chapters[base_name] = True
                html_filename = base_name + '.html'
                output_filepath = os.path.join(self.output_dir, html_filename)
                write_file(output_filepath, html)
                self.log.info(f"Converted {os.path.basename(filename)} to {os.path.basename(html_filename)}.")
            else:
                # Directly copy over files that are not markdown files
                try:
                    output_filepath = os.path.join(self.output_dir, os.path.basename(filename))
                    if not os.path.exists(output_filepath):
                        copyfile(filename, output_filepath)
                except:
                    pass
        self.log.info("Finished processing OBS Markdown files.")


    def convert_markdown(self):
        logging.info("Converting Markdown files…")

        # Find the first directory that has md files.
        files = get_files(directory=self.files_dir, exclude=self.EXCLUDED_FILES)
        # convert_only_list = self.check_for_exclusive_convert()
        convert_only_list = [] # Not totally sure what the above line did

        current_dir = os.path.dirname(os.path.realpath(__file__))
        with open(os.path.join(current_dir, 'templates', 'template.html')) as template_file:
            # Just a very simple template with $title and $content place-holders
            html_template = string.Template(template_file.read())

        found_chapters = {}
        for filepath in sorted(files):
            if filepath.endswith('.md'):
                base_name_part = os.path.splitext(os.path.basename(filepath))[0]
                filename = base_name_part + '.md'
                if convert_only_list and (filename not in convert_only_list):  # see if this is a file we are to convert
                    continue
                html_filename = base_name_part + '.html'
                logging.debug(f"Converting '{filename}' to '{html_filename}' …")

                # Convert files that are markdown files
                with open(filepath, 'rt') as md_file:
                    md = md_file.read()
                if self.repo_subject in ['Translation_Academy',]:
                    html = markdown2.markdown(md, extras=['markdown-in-html', 'tables'])
                    if prefix and debug_mode_flag:
                        write_file(os.path.join(self.debug_dir, base_name_part+'.1.html'), html)
                else:
                    html = markdown.markdown(md)
                html = html_template.safe_substitute(title=self.repo_subject, content=html)
                if prefix and debug_mode_flag:
                    write_file(os.path.join(self.debug_dir, base_name_part+'.2.html'), html)

                # Change headers like <h1><a id="verbs"/>Verbs</h1> to <h1 id="verbs">Verbs</h1>
                soup = BeautifulSoup(html, 'html.parser')
                for tag in soup.findAll('a', {'id': True}):
                    if tag.parent and tag.parent.name in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
                        tag.parent['id'] = tag['id']
                        tag.parent['class'] = tag.parent.get('class', []) + ['section-header']
                        tag.extract()
                html = str(soup)

                base_name_part = os.path.splitext(os.path.basename(filepath))[0]
                found_chapters[base_name_part] = True
                output_file = os.path.join(self.output_dir, html_filename)
                write_file(output_file, html)
                self.log.info(f"Converted {filename} to {html_filename}.")
            else:
                # Directly copy over files that are not markdown files
                try:
                    output_file = os.path.join(self.output_dir, os.path.basename(filepath))
                    if not os.path.exists(output_file):
                        copyfile(filepath, output_file)
                except:
                    pass
        self.log.info("Finished processing Markdown files.")
