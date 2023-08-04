#!/usr/bin/env python3
#
#  Copyright (c) 2020 unfoldingWord
#  http://creativecommons.org/licenses/MIT/
#  See LICENSE file for details.
#
#  Contributors:
#  Richard Mahn <rich.mahn@unfoldingword.org>

"""
This script generates the HTML and PDF TQ documents
"""
import os
import markdown
from glob import glob
from bs4 import BeautifulSoup
from door43_tools.subjects import TRANSLATION_QUESTIONS
from .pdf_converter import PdfConverter
from general_tools.html_tools import increment_headers


class TqPdfConverter(PdfConverter):
    my_subject = TRANSLATION_QUESTIONS

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def get_sample_text(self):
        md_file = os.path.join(self.main_resource.repo_dir, self.project_id, '01.md')
        html = markdown.markdownFromFile(md_file)
        soup = BeautifulSoup(html, 'html.parser')
        return soup.find('p').text

    def get_appendix_rcs(self):
        pass

    def get_body_html(self):
        self.log.info('Creating TQ for {0}...'.format(self.file_project_and_ref))
        return self.get_tq_html()

    def get_tq_html(self):
        tq_html = ''
        if self.project_id:
            projects = [self.main_resource.find_project(self.project_id)]
        else:
            projects = self.main_resource.projects
        for project_idx, project in enumerate(projects):
            project_id = project['identifier']
            book_title = self.get_project_title(project)
            project_dir = os.path.join(self.main_resource.repo_dir, project_id)
            chapter_dirs = sorted(glob(os.path.join(project_dir, '*')))
            tq_html += f'''
<section id="{self.language_id}-{self.name}-{project_id}" class="tq-book">
    <article id="{self.language_id}-{self.name}-{project_id}-cover" class="resource-title-page no-header-footer"">
        <img src="{self.main_resource.logo_url}" class="logo" alt="UTQ">
        <h1{' class="section-header"' if project_idx == 0 else ''}>{self.title}</h1>
        <h2 class="section-header no-header">{book_title}</h2>
    </article>
'''
            for chapter_dir in chapter_dirs:
                chapter = os.path.basename(chapter_dir).lstrip('0')
                tq_html += f'''
    <section id="{self.language_id}-{self.name}-{project_id}-{self.pad(chapter)}" class="tq-chapter">
        <h3 class="section-header{' no-toc' if len(projects) > 1 else ''}">{book_title} {chapter}</h3>
'''
                verse_files = sorted(glob(os.path.join(chapter_dir, '*.md')))
                for verse_file in verse_files:
                    verse = os.path.splitext(os.path.basename(verse_file))[0].lstrip('0')
                    tq_article = markdown.markdownFromFile(verse_file)
                    tq_article = increment_headers(tq_article, 3)
                    tq_title = f'{book_title} {chapter}:{verse}'
                    tq_rc_link = f'rc://{self.language_id}/tq/help/{project_id}/{self.pad(chapter, project_id)}/{verse.zfill(3)}'
                    tq_rc = self.add_rc(tq_rc_link, tq_article, tq_title)
                    tq_html += f'''
        <article id="{tq_rc.article_id}" class="tq-verse">
            <h3>{tq_rc.title}</h3>
            {tq_article}
        </article>
'''
                tq_html += '''
    </section>
'''
            tq_html += '''
</section>
'''
        self.log.info('Done generating TQ HTML.')
        return tq_html
