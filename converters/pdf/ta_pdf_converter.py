#!/usr/bin/env python3
#
#  Copyright (c) 2020 unfoldingWord
#  http://creativecommons.org/licenses/MIT/
#  See LICENSE file for details.
#
#  Contributors:
#  Richard Mahn <rich.mahn@unfoldingword.org>

"""
This script generates the HTML and PDF TA documents
"""
import os
import yaml
import markdown2
from bs4 import BeautifulSoup
from door43_tools.subjects import TRANSLATION_ACADEMY
from .pdf_converter import PdfConverter
from general_tools.file_utils import read_file


class TaPdfConverter(PdfConverter):
    my_subject = TRANSLATION_ACADEMY

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.section_count = 0
        self.config = None
        self.toc_html = ''

    def get_sample_text(self):
        files = [os.path.join(self.main_resource.repo_dir, 'intro', 'translation-guidelines', '01.md'),
                 os.path.join(self.main_resource.repo_dir, 'translate', 'figs-verbs', '01.md'),
                 os.path.join(self.main_resource.repo_dir, 'translate', 'transle-help', '01.md')]
        for file in files:
            if os.path.exists(file):
                html = markdown2.markdown_path(file)
                soup = BeautifulSoup(html, 'html.parser')
                return soup.find('p').text
        return ''

#     def get_toc_from_yaml(self):
#         toc_html = ''
#         projects = self.main_resource.projects
#         self.section_count = 0
#         for idx, project in enumerate(projects):
#             project_path = os.path.join(self.main_resource.repo_dir, project['identifier'])
#             toc = yaml.full_load(read_file(os.path.join(project_path, 'toc.yaml')))
#             if not toc_html:
#                 toc_html = f'''
#                 <article id="contents">
#                   <h1>{toc['title']}</h1>
#                   <ul id="contents-top-ul">
# '''
#             toc_html += f'<li><a href="#{self.lang_code}-ta-man-{project["identifier"]}-cover"><span>{project["title"]}</span></a>'
#             toc_html += self.get_toc_for_section(toc)
#             toc_html += '</li>'
#         toc_html += '</ul></article>'
#         return toc_html
#
#     def get_toc_for_section(self, section):
#         toc_html = ''
#         if 'sections' not in section:
#             return toc_html
#         toc_html = '<ul>'
#         for section in section['sections']:
#             title = section['title']
#             self.section_count += 1
#             link = f'section-container-{self.section_count}'
#             toc_html += f'<li><a href="#{link}"><span>{title}</span></a>{self.get_toc_for_section(section)}</li>'
#         toc_html += '</ul>'
#         return toc_html

#    def finish_up(self):
#        self.generate_docx()

    def get_body_html(self):
        self.log.info('Generating TA html...')
        # self.toc_html = self.get_toc_from_yaml()
        ta_html = self.get_ta_html()
        return ta_html

    def generate_all_files(self):
        self.project_id = ''
        self.errors = {}
        self.bad_highlights = {}
        self.rcs = {}
        self.appendix_rcs = {}
        self.all_rcs = {}
        self.generate_html_file()
        self.generate_pdf_file()

    def get_ta_html(self):
        ta_html = f'''
<section id="{self.lang_code}-ta-man">
    {self.get_articles()}
</section>
'''
        return ta_html

    def get_articles(self):
        articles_html = ''
        projects = self.main_resource.projects
        self.section_count = 0
        for idx, project in enumerate(projects):
            project_id = project['identifier']
            project_path = os.path.join(self.main_resource.repo_dir, project_id)
            toc = yaml.full_load(read_file(os.path.join(project_path, 'toc.yaml')))
            self.config = yaml.full_load(read_file(os.path.join(project_path, 'config.yaml')))
            articles_html += f'''
<article id="{self.lang_code}-{project_id}-cover" class="manual-cover cover">
    <img src="{self.main_resource.logo_url}" alt="{project_id}" />
    <h1>{self.title}</h1>
    <h2 class="section-header" toc-level="1">{project['title']}</h2>
</article>
'''
            articles_html += self.get_articles_from_toc(project_id, toc)
        return articles_html

    def get_articles_from_toc(self, project_id, section, toc_level=2):
        if 'sections' not in section:
            return ''
        source_rc = self.create_rc(f'rc://{self.lang_code}/ta/man/{project_id}/toc.yaml')
        articles_html = ''
        for subsection in section['sections']:
            self.section_count += 1
            if 'link' in subsection:
                link = subsection['link']
                title = self.get_title(project_id, link, subsection['title'])
            else:
                link = f'section-container-{self.section_count}'
                title = subsection['title']
            rc_link = f'rc://{self.lang_code}/ta/man/{project_id}/{link}'
            rc = self.add_rc(rc_link, title=title)
            if 'link' in subsection:
                self.get_ta_article_html(rc, source_rc, self.config, toc_level)
            if 'sections' in subsection:
                sub_articles = self.get_articles_from_toc(project_id, subsection, toc_level + 1)
                section_header = ''
                if not rc.article:
                    section_header = f'''
    <h2 class="section-header" toc-level="{toc_level}">{title}</h2>
'''
                articles_html += f'''
<section id="{rc.article_id}-section">
    {section_header}
    {rc.article}
    {sub_articles}
</section>
'''
            elif rc.article:
                articles_html += rc.article
        return articles_html

    def get_title(self, project, link, alt_title):
        title_file = os.path.join(self.main_resource.repo_dir, project, link, 'title.md')
        title = None
        if os.path.isfile(title_file):
            title = read_file(title_file).strip()
        if not title:
            title = alt_title.strip()
        return title

    # def get_toc_html(self, body_html):
    #     return self.toc_html
