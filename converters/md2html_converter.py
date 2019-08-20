import os
import string
from shutil import copyfile
import re

import markdown
import markdown2
from bs4 import BeautifulSoup
import requests

from rq_settings import prefix, debug_mode_flag
from general_tools.file_utils import read_file, write_file, get_files
from converters.converter import Converter
from converters.convert_naked_urls import fix_naked_urls
from app_settings.app_settings import AppSettings



class Md2HtmlConverter(Converter):

    def convert(self):
        if self.repo_subject == 'Open_Bible_Stories':
            # TODO: What is the difference here?
            self.convert_obs()
            return True
        elif self.repo_subject in ('OBS_Translation_Notes', 'OBS_Translation_Questions'):
            self.convert_obsNotes()
            return True
        elif '_Lexicon' in self.repo_subject:
            self.convert_lexicon()
            return True
        else:
            self.convert_markdown()
            return True
    # end of Md2HtmlConverter.convert()


    def convert_obs(self):
        self.log.info("Converting OBS markdown files…")

        # Find the first directory that has md files.
        files = get_files(directory=self.files_dir, exclude=self.EXCLUDED_FILES)

        current_dir = os.path.dirname(os.path.realpath(__file__))
        with open(os.path.join(current_dir, 'templates', 'template.html')) as template_file:
            html_template = string.Template(template_file.read())

        # found_chapters = {}
        for filepath in sorted(files):
            if filepath.endswith('.md'):
                # Convert files that are markdown files
                base_name_part = os.path.splitext(os.path.basename(filepath))[0]
                # found_chapters[base_name] = True
                try: md = read_file(filepath)
                except Exception as e:
                    self.log.error(f"Error reading {base_name_part+'.md'}: {e}")
                    continue
                html = markdown.markdown(md)
                html = html_template.safe_substitute(
                                            title=self.repo_subject.replace('_',' '),
                                            content=html)
                html_filename = base_name_part + '.html'
                output_filepath = os.path.join(self.output_dir, html_filename)
                write_file(output_filepath, html)
                self.log.info(f"Converted {os.path.basename(filepath)} to {os.path.basename(html_filename)}.")
            else:
                # Directly copy over files that are not markdown files
                try:
                    output_filepath = os.path.join(self.output_dir, os.path.basename(filepath))
                    if not os.path.exists(output_filepath):
                        copyfile(filepath, output_filepath)
                except:
                    pass
        self.log.info("Finished processing OBS Markdown files.")
    # end of Md2HtmlConverter.convert_obs()


    def convert_obsNotes(self):
        """
        This converter is used for OBS_tn and OBS_tq
        """
        self.log.info("Converting OBSNotes markdown files…")

        current_dir = os.path.dirname(os.path.realpath(__file__))
        with open(os.path.join(current_dir, 'templates', 'template.html')) as template_file:
            html_template = string.Template(template_file.read())

        # First handle files in the root folder
        files = os.listdir(self.files_dir)
        for filename in sorted(files):
            if filename in self.EXCLUDED_FILES:
                continue # ignore it
            filepath = os.path.join(self.files_dir, filename)
            if filename.endswith('.md'):
                # Convert files that are markdown files
                base_name_part = os.path.splitext(os.path.basename(filepath))[0]
                # found_chapters[base_name] = True
                try: md = read_file(filepath)
                except Exception as e:
                    self.log.error(f"Error reading {base_name_part+'.md'}: {e}")
                    continue
                html = markdown.markdown(md)
                html = html_template.safe_substitute(
                                            title=self.repo_subject.replace('_',' '),
                                            content=html)
                html_filename = base_name_part + '.html'
                output_filepath = os.path.join(self.output_dir, html_filename)
                write_file(output_filepath, html)
                self.log.info(f"Converted {os.path.basename(filepath)} to {os.path.basename(html_filename)}.")
            else:
                # Directly copy over files that are not markdown files
                try:
                    output_filepath = os.path.join(self.output_dir, os.path.basename(filepath))
                    if not os.path.exists(output_filepath):
                        copyfile(filepath, output_filepath)
                except:
                    pass

        # # Now handle the story folders
        # # found_chapters = {}
        # for story_number in range(1, 50+1):
        #     story_number_string = str(story_number).zfill(2)
        #     story_folder_path = os.path.join(self.files_dir, f'{story_number_string}/')
        #     if not os.path.isdir(story_folder_path):
        #         self.log.warning(f"Unable to find folder '{story_number_string}/'")
        #         continue
        #     for filename in sorted(os.listdir(story_folder_path)):
        #         filepath = os.path.join(story_folder_path, filename)
        #         print(f"Filename={filename} at {filepath}")
        #         if filename.endswith('.md'):
        #             # Convert files that are markdown files
        #             base_name_part = os.path.splitext(os.path.basename(filepath))[0]
        #             # found_chapters[base_name] = True
        #             try: md = read_file(filepath)
        #             except Exception as e:
        #                 self.log.error(f"Error reading {base_name_part+'.md'}: {e}")
        #                 continue
        #             html = markdown.markdown(md)
        #             html = html_template.safe_substitute(
        #                                         title=self.repo_subject.replace('_',' '),
        #                                         content=html)
        #             html_filename = f'{story_number_string}-{base_name_part}.html'
        #             output_filepath = os.path.join(self.output_dir, html_filename)
        #             write_file(output_filepath, html)
        #             self.log.info(f"Converted {os.path.basename(filepath)} to {os.path.basename(html_filename)}.")
        #         else:
        #             self.log.error(f"Unexpected '{filename}' file in {story_number_string}/")
        #             # Directly copy over files that are not markdown files
        #             try:
        #                 output_filepath = os.path.join(self.output_dir, os.path.basename(filepath))
        #                 if not os.path.exists(output_filepath):
        #                     copyfile(filepath, output_filepath)
        #             except:
        #                 pass
        self.log.info("Finished processing OBSNotes Markdown files.")
    # end of Md2HtmlConverter.convert_obsNotes()


    def convert_markdown(self):
        self.log.info("Converting Markdown files…")

        # Find the first directory that has md files.
        files = get_files(directory=self.files_dir, exclude=self.EXCLUDED_FILES)
        # convert_only_list = self.check_for_exclusive_convert()
        convert_only_list = [] # Not totally sure what the above line did

        current_dir = os.path.dirname(os.path.realpath(__file__))
        with open(os.path.join(current_dir, 'templates', 'template.html')) as template_file:
            # Just a very simple template with $title and $content place-holders
            html_template = string.Template(template_file.read())

        # found_chapters = {}
        for filepath in sorted(files):
            if filepath.endswith('.md'):
                base_name_part = os.path.splitext(os.path.basename(filepath))[0]
                filename = base_name_part + '.md'
                if convert_only_list and (filename not in convert_only_list):  # see if this is a file we are to convert
                    continue
                html_filename = base_name_part + '.html'
                AppSettings.logger.debug(f"Converting '{filename}' to '{html_filename}' …")

                # Convert files that are markdown files
                try: md = read_file(filepath)
                except Exception as e:
                    self.log.error(f"Error reading {filename}: {e}")
                    continue
                # if 0: # test code -- creates html1
                #     headers = {"content-type": "application/json"}
                #     url = "http://bg.door43.org/api/v1/markdown"
                #     payload = {
                #         'Context': "",
                #         'Mode': "normal",
                #         'Text': md,
                #         'Wiki': False
                #         }
                #     # url = "http://bg.door43.org/api/v1/markdown/raw"
                #     AppSettings.logger.debug(f"Making callback to {url} with payload:")
                #     AppSettings.logger.debug(json.dumps(payload)[:256] + '…')
                #     try:
                #         response = requests.post(url, json=payload, headers=headers)
                #         # response = requests.post(url, data=md, headers=headers)
                #     except requests.exceptions.ConnectionError as e:
                #         AppSettings.logger.critical(f"Markdown->HTML connection error: {e}")
                #         response = None
                #     if response:
                #         #AppSettings.logger.info(f"response.status_code = {response.status_code}, response.reason = {response.reason}")
                #         #AppSettings.logger.debug(f"response.headers = {response.headers}")
                #         AppSettings.logger.debug(f"response.text = {response.text[:256] + '…'}")
                #         html1 = response.text
                #         if response.status_code != 200:
                #             AppSettings.logger.critical(f"Failed to submit Markdown->HTML job:"
                #                                         f" {response.status_code}={response.reason}")
                #         # callback_status = response.status_code
                #         # if (callback_status >= 200) and (callback_status < 299):
                #         #     AppSettings.logger.debug("Markdown->HTML callback finished.")
                #         # else:
                #         #     AppSettings.logger.error(f"Error calling callback code {callback_status}: {response.reason}")
                #     else: # no response
                #         AppSettings.logger.error("Submission of job to Markdown->HTML got no response")
                if 1: # old/existing code -- creates html2
                    if self.repo_subject in ['Translation_Academy',]:
                        html2 = markdown2.markdown(md, extras=['markdown-in-html', 'tables'])
                        if prefix and debug_mode_flag:
                            write_file(os.path.join(self.debug_dir, base_name_part+'.1.html'), html2)
                    else:
                        html2 = markdown.markdown(md)
                # if 0:
                #     if html2 == html1:
                #         AppSettings.logger.debug("HTML responses are identical.")
                #     else:
                #         AppSettings.logger.error(f"HTML responses differ: {len(html1)} and {len(html2)}")
                #         AppSettings.logger.debug(repr(html1)[:256] + ' …… ' + repr(html1)[-256:])
                #         AppSettings.logger.debug(repr(html2)[:256] + ' …… ' + repr(html2)[-256:])
                #     try: html = html1
                #     except UnboundLocalError: html = html2
                # else:
                html = html2

                html = html_template.safe_substitute(
                                        title=self.repo_subject.replace('_',' '),
                                        content=html)
                if prefix and debug_mode_flag:
                    write_file(os.path.join(self.debug_dir, base_name_part+'.2.html'), html)

                html = fix_naked_urls(html)
                if prefix and debug_mode_flag:
                    write_file(os.path.join(self.debug_dir, base_name_part+'.3.html'), html)

                # Change headers like <h1><a id="verbs"/>Verbs</h1> to <h1 id="verbs">Verbs</h1>
                soup = BeautifulSoup(html, 'html.parser')
                for tag in soup.findAll('a', {'id': True}):
                    if tag.parent and tag.parent.name in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
                        tag.parent['id'] = tag['id']
                        tag.parent['class'] = tag.parent.get('class', []) + ['section-header']
                        tag.extract()
                html = str(soup)

                # Write the file
                base_name_part = os.path.splitext(os.path.basename(filepath))[0]
                # found_chapters[base_name_part] = True
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
    # end of Md2HtmlConverter.convert_markdown()


    def convert_lexicon(self):
        """
        Does not convert md files starting with G or H and a digit.
        """
        self.log.info("Converting Lexicon files…")

        # Find the first directory that has md files.
        files = get_files(directory=self.files_dir, exclude=self.EXCLUDED_FILES)
        # convert_only_list = self.check_for_exclusive_convert()
        convert_only_list = [] # Not totally sure what the above line did

        current_dir = os.path.dirname(os.path.realpath(__file__))
        with open(os.path.join(current_dir, 'templates', 'template.html')) as template_file:
            # Just a very simple template with $title and $content place-holders
            html_template = string.Template(template_file.read())

        for filepath in sorted(files):
            if filepath.endswith('.md'):
                base_name_part = os.path.splitext(os.path.basename(filepath))[0]
                # We don't process the actual thousands of lexicon entries
                if base_name_part[0] in ('G','H') and base_name_part[1].isdigit():
                    # print(f"Skipping {base_name_part}")
                    continue
                filename = base_name_part + '.md'
                if convert_only_list and (filename not in convert_only_list):  # see if this is a file we are to convert
                    continue
                html_filename = base_name_part + '.html'
                AppSettings.logger.debug(f"Converting '{filename}' to '{html_filename}' …")

                # Convert files that are markdown files
                try: md = read_file(filepath)
                except Exception as e:
                    self.log.error(f"Error reading {filename}: {e}")
                    continue
                # if 0: # test code -- creates html1
                #     headers = {"content-type": "application/json"}
                #     url = "http://bg.door43.org/api/v1/markdown"
                #     payload = {
                #         'Context': "",
                #         'Mode': "normal",
                #         'Text': md,
                #         'Wiki': False
                #         }
                #     # url = "http://bg.door43.org/api/v1/markdown/raw"
                #     AppSettings.logger.debug(f"Making callback to {url} with payload:")
                #     AppSettings.logger.debug(json.dumps(payload)[:256] + '…')
                #     try:
                #         response = requests.post(url, json=payload, headers=headers)
                #         # response = requests.post(url, data=md, headers=headers)
                #     except requests.exceptions.ConnectionError as e:
                #         AppSettings.logger.critical(f"Markdown->HTML connection error: {e}")
                #         response = None
                #     if response:
                #         #AppSettings.logger.info(f"response.status_code = {response.status_code}, response.reason = {response.reason}")
                #         #AppSettings.logger.debug(f"response.headers = {response.headers}")
                #         AppSettings.logger.debug(f"response.text = {response.text[:256] + '…'}")
                #         html1 = response.text
                #         if response.status_code != 200:
                #             AppSettings.logger.critical(f"Failed to submit Markdown->HTML job:"
                #                                         f" {response.status_code}={response.reason}")
                #         # callback_status = response.status_code
                #         # if (callback_status >= 200) and (callback_status < 299):
                #         #     AppSettings.logger.debug("Markdown->HTML callback finished.")
                #         # else:
                #         #     AppSettings.logger.error(f"Error calling callback code {callback_status}: {response.reason}")
                #     else: # no response
                #         AppSettings.logger.error("Submission of job to Markdown->HTML got no response")
                if 1: # old/existing code -- creates html2
                    if self.repo_subject in ['Translation_Academy',]:
                        html2 = markdown2.markdown(md, extras=['markdown-in-html', 'tables'])
                        if prefix and debug_mode_flag:
                            write_file(os.path.join(self.debug_dir, base_name_part+'.1.html'), html2)
                    else:
                        html2 = markdown.markdown(md)
                # if 0:
                #     if html2 == html1:
                #         AppSettings.logger.debug("HTML responses are identical.")
                #     else:
                #         AppSettings.logger.error(f"HTML responses differ: {len(html1)} and {len(html2)}")
                #         AppSettings.logger.debug(repr(html1)[:256] + ' …… ' + repr(html1)[-256:])
                #         AppSettings.logger.debug(repr(html2)[:256] + ' …… ' + repr(html2)[-256:])
                #     try: html = html1
                #     except UnboundLocalError: html = html2
                # else:
                html = html2

                html = html_template.safe_substitute(
                                        title=self.repo_subject.replace('_',' '),
                                        content=html)
                if prefix and debug_mode_flag:
                    write_file(os.path.join(self.debug_dir, base_name_part+'.2.html'), html)

                if '_index' in filepath:
                    html = self.fix_lexicon_markdown_urls(html)
                    if prefix and debug_mode_flag:
                        write_file(os.path.join(self.debug_dir, base_name_part+'.3.html'), html)

                html = fix_naked_urls(html)
                if prefix and debug_mode_flag:
                    write_file(os.path.join(self.debug_dir, base_name_part+'.4.html'), html)

                # Change headers like <h1><a id="verbs"/>Verbs</h1> to <h1 id="verbs">Verbs</h1>
                soup = BeautifulSoup(html, 'html.parser')
                for tag in soup.findAll('a', {'id': True}):
                    if tag.parent and tag.parent.name in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
                        tag.parent['id'] = tag['id']
                        tag.parent['class'] = tag.parent.get('class', []) + ['section-header']
                        tag.extract()
                html = str(soup)

                # Write the file
                base_name_part = os.path.splitext(os.path.basename(filepath))[0]
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
    # end of Md2HtmlConverter.convert_lexicon()


    def fix_lexicon_markdown_urls(self, content):
        """
        Change lexicon links that point to .md URL to instead point to a default page
            with the xxx.md link added
        """
        self.log.info("Md2HtmlConverter.fix_lexicon_markdown_urls()…")
        if 'href="https://git.door43.org/' not in content:
            self.log.error(f"Md2HtmlConverter.write_lexicon_view_entry_file() has unexpected links: {content}")

        new_content = content
        # new_content = re.sub(r'href="(.+?).md"', r'''href="javascript.ViewMarkdownFile('\1.md');"''', content)
        # new_content = re.sub(r'href="(.+?).md"', r'''class="mdLink" href="\1.md" onclick="ViewMarkdownFile('\1.md');"''', content)
        md_pattern = re.compile(r'href="(.+?).md"')
        # TODO: Need to double-check that '/content/' is always included in the .md path
        #       Could maybe use '/raw/' (but not '/branch/')
        path_split_string = '/content/'
        # "a.lexIndexLink {float:left; width:100px;}" needs to go into door43.org/_site/css/project-page.css
        fixed_string = 'class="lexIndexLink" href="view_lexicon_entry.html?path='
        adj_len = len(fixed_string) + 10 # How far to step thru the file (so don't find the same .md string twice)
        search_from = 0
        while True:
            match = md_pattern.search(new_content, search_from)
            if not match: break
            # print(search_from, match.start(), match.end(), len(new_content))

            bits = match.group(1).split(path_split_string)
            # print("bits", bits)
            assert len(bits) == 2 # Will fail below if not
            fixed_path = bits[0] # + path_split_string
            # print(fixed_string + bits[1] + '.md"')
            new_content = new_content[:match.start()] \
                + fixed_string + path_split_string + bits[1] + '.md"' \
                + new_content[match.end():]
            search_from = match.start() + adj_len

        if new_content != content:
            # print("fix_markdown_urls now has", new_content)
            self.write_lexicon_view_entry_file(fixed_path)
        return new_content
    # end of Md2HtmlConverter.fix_markdown_urls()


    def write_lexicon_view_entry_file(self, path_prefix):
        """
        Write the dummy html file that will be used to display markdown lexicon entries.
        """
        self.log.info(f"Md2HtmlConverter.write_lexicon_view_entry_file({path_prefix})…")

        with open(os.path.join(self.output_dir, 'view_lexicon_entry.html'), 'wt') as output_file:
            output_file.write(f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Lexicon entry</title>
</head>
<body>
<script type="text/javascript" src="/js/jquery.min.js"></script>
<script>
    function getPassedMarkdownURL() {{
        var href = window.location.href;
        var n = href.indexOf('?path='); // returns -1 if none found
        var newURL =  '{path_prefix}' + href.substring(n+6); // From n+6 to end
        return newURL;
    }}
    function getPassedMarkdownLink() {{
        var newURL =  getPassedMarkdownURL();
        var markdownLink = '<a href="' + newURL + '">' + newURL + '</a>';
        return markdownLink;
    }}
    // Adapted from https://stackoverflow.com/questions/4533018/how-to-read-a-text-file-from-server-using-javascript
    getTxt = function (){{
        $.ajax({{
            url:getPassedMarkdownURL(),
            success: function (data){{
                document.getElementById('content').innerHTML = marked(data);
            }}
        }});
    }}
</script>
<div id="content">
    <p>We need to display the markdown lexicon entry from
        <script>document.write(getPassedMarkdownLink());</script></p>
    <p><script>document.write(getTxt());</script></p>
    </div>
<script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
</body>
</html>
''')
    # end of Md2HtmlConverter.write_lexicon_view_entry_file()
# end of Md2HtmlConverter class
