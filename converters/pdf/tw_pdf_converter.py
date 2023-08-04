#!/usr/bin/env python3
#
#  Copyright (c) 2020 unfoldingWord
#  http://creativecommons.org/licenses/MIT/
#  See LICENSE file for details.
#
#  Contributors:
#  Richard Mahn <rich.mahn@unfoldingword.org>

"""
This script generates the HTML and PDF TW documents
"""
import os
import markdown
from bs4 import BeautifulSoup
from glob import glob
from collections import OrderedDict
from .pdf_converter import PdfConverter
from door43_tools.subjects import TRANSLATION_WORDS

category_titles = OrderedDict({
    'kt': 'Key Terms',
    'names': 'Names',
    'other': 'Other'
})


class TwPdfConverter(PdfConverter):
    my_subject = TRANSLATION_WORDS

    def get_body_html(self):
        self.log.info('Creating TW for {0}...'.format(self.file_project_and_ref))
        return self.get_tw_html()

    def get_sample_text(self):
        filepath = os.path.join(self.main_resource.repo_dir, 'bible', 'kt', 'god.md')
        try:
            html = markdown.markdownFromFile(filepath)
        except:
            filepath = os.path.join(self.main_resource.repo_dir, 'LICENSE.md')
            html = markdown.markdownFromFile(filepath)
        soup = BeautifulSoup(html, 'html.parser')
        return soup.find('p').text

    def get_tw_html(self):
        tw_html = f'''
<section id="{self.language_id}-{self.name}" class="tw-category">
'''
        project_id = self.main_resource.projects[0]['identifier']
        for category in category_titles.keys():
            category_dir = os.path.join(self.main_resource.repo_dir, project_id, category)
            category_title = category_titles[category]
            tw_html += f'''
    <section id="{self.language_id}-{self.name}-{category}" class="tw-category">
        <article id="{self.language_id}-{self.name}-{category}-cover" class="resource-title-page no-header-footer">
            <img src="{self.main_resource.logo_url}" class="logo" alt="UTW">
            <h1{' class="section-header"' if category == list(category_titles.keys())[0] else ''}>{self.title}</h1>
            <h2 class="section-header">{category_title}</h2>
        </article>
'''
            article_files = sorted(glob(os.path.join(category_dir, '*.md')))
            tw_by_title = {}
            for article_file in article_files:
                article_id = os.path.splitext(os.path.basename(article_file))[0]
                tw_rc_link = f'rc://{self.language_id}/tw/dict/{project_id}/{category}/{article_id}'
                tw_rc = self.add_rc(tw_rc_link)
                self.get_tw_article_html(tw_rc, increment_header_depth=2)
                tw_by_title[tw_rc.title] = tw_rc
            tw_sorted_titles = sorted(tw_by_title.keys(), key=lambda s: s.casefold())
            for title in tw_sorted_titles:
                tw_html += tw_by_title[title].article
            tw_html += '''
    </section>
'''
        tw_html += '''
</section>
'''
        self.log.info('Done generating TW HTML.')
        return tw_html
