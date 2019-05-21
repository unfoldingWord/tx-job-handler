import os
import tempfile
from bs4 import BeautifulSoup
from shutil import copyfile

from rq_settings import prefix, debug_mode_flag
from global_settings.global_settings import GlobalSettings
from general_tools.file_utils import write_file, remove_tree, get_files
from converters.converter import Converter
from tx_usfm_tools.transform import UsfmTransform


class Usfm2HtmlConverter(Converter):

    def convert(self):
        GlobalSettings.logger.debug("Processing the Bible USFM files …")

        # Find the first directory that has usfm files.
        files = get_files(directory=self.files_dir, exclude=self.EXCLUDED_FILES)
        # convert_only_list = self.check_for_exclusive_convert()
        convert_only_list = [] # Not totally sure what the above line did

        current_dir = os.path.dirname(os.path.realpath(__file__))
        with open(os.path.join(current_dir, 'templates', 'template.html')) as template_file:
            # Simple HTML template which includes $title and $content fields
            template_html = template_file.read()

        # Convert usfm files and copy across other files
        num_successful_books = num_failed_books = 0
        for filename in sorted(files):
            if filename.endswith('.usfm'):
                base_name = os.path.basename(filename)
                if convert_only_list and (base_name not in convert_only_list):  # see if this is a file we are to convert
                    continue

                # Convert the USFM file
                self.log.info(f"Converting Bible USFM file: {base_name} …") # Logger also issues DEBUG msg
                # Copy just the single file to be converted into a single scratch folder
                scratch_dir = tempfile.mkdtemp(prefix='tX_convert_usfm_scratch_')
                delete_scratch_dir_flag = True # Set to False for debugging this code
                copyfile(filename, os.path.join(scratch_dir, os.path.basename(filename)))
                filebase = os.path.splitext(os.path.basename(filename))[0]
                # Do the actual USFM -> HTML conversion
                warning_list = UsfmTransform.buildSingleHtml(scratch_dir, scratch_dir, filebase)
                if warning_list:
                    for warning_msg in warning_list:
                        self.log.warning(f"{filebase} - {warning_msg}")

                # This code seems to be cleaning up or adjusting the converted HTML file
                html_filename = filebase + '.html'
                with open(os.path.join(scratch_dir, html_filename), 'rt', encoding='utf-8') as html_file:
                    converted_html = html_file.read()
                converted_html_length = len(converted_html)
                # GlobalSettings.logger.debug(f"### Usfm2HtmlConverter got converted html of length {converted_html_length:,}")
                # GlobalSettings.logger.debug(f"Got converted html: {converted_html[:500]}{' …' if len(converted_html)>500 else ''}")
                if '</p></p></p>' in converted_html:
                    GlobalSettings.logger.debug(f"Usfm2HtmlConverter got multiple consecutive paragraph closures in converted {html_filename}")
                # Now what are we doing with the converted html ???
                template_soup = BeautifulSoup(template_html, 'html.parser')
                template_soup.head.title.string = self.repo_subject
                converted_soup = BeautifulSoup(converted_html, 'html.parser')
                content_div = template_soup.find('div', id='content')
                content_div.clear()
                if converted_soup and converted_soup.body:
                    content_div.append(converted_soup.body)
                    content_div.body.unwrap()
                    num_successful_books += 1
                else:
                    content_div.append("ERROR! NOT CONVERTED!")
                    self.log.warning(f"USFM parsing or conversion error for {base_name}")
                    GlobalSettings.logger.debug(f"Got converted html: {converted_html[:600]}{' …' if len(converted_html)>600 else ''}")
                    if not converted_soup:
                        GlobalSettings.logger.debug(f"No converted_soup")
                    elif not converted_soup.body:
                        GlobalSettings.logger.debug(f"No converted_soup.body")
                    # from bs4.diagnose import diagnose
                    # diagnose(converted_html)
                    num_failed_books += 1
                output_filepath = os.path.join(self.output_dir, html_filename)
                #print("template_soup type is", type(template_soup)) # <class 'bs4.BeautifulSoup'>
                template_soup_string = str(template_soup)
                write_file(output_filepath, template_soup_string)
                template_soup_string_length = len(template_soup_string)
                # GlobalSettings.logger.debug(f"### Usfm2HtmlConverter wrote souped-up html of length {template_soup_string_length:,} from {converted_html_length:,}")
                if '</p></p></p>' in template_soup_string:
                    GlobalSettings.logger.warning(f"Usfm2HtmlConverter got multiple consecutive paragraph closures in {html_filename}")
                if template_soup_string_length < converted_html_length * 0.70: # What is the 25% or so that's lost ???
                    GlobalSettings.logger.debug(f"### Usfm2HtmlConverter wrote souped-up html of length {template_soup_string_length:,} from {converted_html_length:,} = {template_soup_string_length*100.0/converted_html_length}%")
                    self.log.error(f"Usfm2HtmlConverter lost converted html for {html_filename}")
                    GlobalSettings.logger.debug(f"Usfm2HtmlConverter {html_filename} was {converted_html_length:,} now {template_soup_string_length:,}")
                    # GlobalSettings.logger.debug(f"Usfm2HtmlConverter {html_filename} was: {converted_html}")
                    write_file(os.path.join(scratch_dir,filebase+'.converted.html'), template_soup_string)
                    if prefix and debug_mode_flag:
                        delete_scratch_dir_flag = False
                #print("Got converted x2 html:", str(template_soup)[:500])
                # self.log.info(f"Converted {os.path.basename(filename)} to {os.path.basename(html_filename)}.")
                if delete_scratch_dir_flag:
                    remove_tree(scratch_dir)
            else:
                # Directly copy over files that are not USFM files
                try:
                    output_filepath = os.path.join(self.output_dir, os.path.basename(filename))
                    if not os.path.exists(output_filepath):
                        copyfile(filename, output_filepath)
                except:
                    pass
        if num_failed_books and not num_successful_books:
            self.log.error(f"Conversion of all books failed!")
        self.log.info(f"Finished processing {num_successful_books} Bible USFM files.")
        return True
