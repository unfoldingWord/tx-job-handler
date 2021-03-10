#!/usr/bin/env python3
#
#  Copyright (c) 2020 unfoldingWord
#  http://creativecommons.org/licenses/MIT/
#  See LICENSE file for details.
#
#  Contributors:
#  Richard Mahn <rich.mahn@unfoldingword.org>

"""
This script generates the HTML and PDF OBS SQ documents
"""
import os
import re
import markdown2
import general_tools.html_tools as html_tools
from door43_tools.subjects import OBS_TRANSLATION_QUESTIONS
from glob import glob
from bs4 import BeautifulSoup
from general_tools import obs_tools
from .pdf_converter import PdfConverter


class ObsTqPdfConverter(PdfConverter):
    my_subject = OBS_TRANSLATION_QUESTIONS

    def get_sample_text(self):
        filepath = os.path.join(self.main_resource.repo_dir, 'content', '01', '01.md')
        try:
            html = markdown2.markdown_path(filepath)
        except:
            filepath = os.path.join(self.main_resource.repo_dir, 'LICENSE.md')
            html = markdown2.markdown_path(filepath)
        soup = BeautifulSoup(html, 'html.parser')
        return soup.find('p').text

    @property
    def name(self):
        return self.main_resource.identifier

    @property
    def title(self):
        return self.main_resource.title

    @property
    def simple_title(self):
        return self.main_resource.simple_title

    @property
    def project_title(self):
        return ''

    def get_body_html(self):
        self.log.info('Generating OBS TN html...')
        return self.get_obs_tq_html()

    def get_obs_tq_html(self):
        obs_tq_html = f'''
<section id="obs-sn">
    <div class="resource-title-page no-header">
        <img src="{self.resources['obs'].logo_url}" class="logo" alt="OBS">
        <h1 class="section-header">{self.simple_title}</h1>
    </div>
'''
        obs_tq_chapter_dirs = sorted(glob(os.path.join(self.main_resource.repo_dir, 'content', '*')))
        for obs_tq_chapter_dir in obs_tq_chapter_dirs:
            if os.path.isdir(obs_tq_chapter_dir):
                chapter_num = os.path.basename(obs_tq_chapter_dir)
                chapter_data = obs_tools.get_obs_chapter_data(self.resources['obs'].repo_dir, chapter_num)
                obs_tq_html += f'''
    <article id="{self.lang_code}-obs-tq-{chapter_num}">
        <h2 class="section-header">{chapter_data['title']}</h2>
'''
                frames = chapter_data['frames']
                for frame_idx, frame in enumerate(frames):
                    frame_num = str(frame_idx+1).zfill(2)
                    frame_title = f'{chapter_num}:{frame_num}'
                    tq_file = os.path.join(obs_tq_chapter_dir, f'{frame_num}.md')
                    tq_html = ''
                    if os.path.isfile(tq_file):
                        tq_html = markdown2.markdown_path(tq_file)
                        tq_html = html_tools.increment_headers(tq_html, 3)
                    if (not frame or not frame['text']) and not tq_html:
                        continue

                    # HANDLE RC LINKS FOR OBS FRAME
                    frame_rc_link = f'rc://{self.lang_code}/obs/book/obs/{chapter_num}/{frame_num}'
                    frame_rc = self.add_rc(frame_rc_link, title=frame_title)
                    # HANDLE RC LINKS FOR NOTES
                    tq_rc_link = f'rc://{self.lang_code}/obs-tq/help/{chapter_num}/{frame_num}'
                    tq_rc = self.add_rc(tq_rc_link, title=frame_title, article=tq_html)

                    obs_text = ''
                    if frame and frame['text']:
                        obs_text = frame['text']
                    # Some OBS TN languages (e.g. English) do not have Translation Words in their TN article
                    # while some do (e.g. French). We need to add them ourselves from the tw_cat file
                    if obs_text:
                        obs_text = f'''
            <div id="{frame_rc.article_id}" class="frame-text">
                {obs_text}
            </div>
'''
                    if tq_html:
                        tq_html = f'''
            <div id="{tq_rc.article_id}-tq" class="frame-tq">
                {tq_html}
            </div>
'''

                    obs_tq_html += f'''
        <div id="{tq_rc.article_id}">
            <h3>{frame_title}</h3>
            {obs_text}
            {tq_html}
        </div>
'''
                    if frame_idx < len(frames) - 1:
                        obs_tq_html += '<hr class="frame-divider"/>\n'
                obs_tq_html += '''
    </article>
'''
        obs_tq_html += '''
</section>
'''
        return obs_tq_html

    def fix_links(self, html):
        # Changes references to chapter/frame in links
        # <a href="1/10">Text</a> => <a href="rc://obs-sn/help/obs/01/10">Text</a>
        # <a href="10-1">Text</a> => <a href="rc://obs-sn/help/obs/10/01">Text</a>
        html = re.sub(r'href="(\d)/(\d+)"', r'href="0\1/\2"', html)  # prefix 0 on single-digit chapters
        html = re.sub(r'href="(\d+)/(\d)"', r'href="\1/0\2"', html)  # prefix 0 on single-digit frames
        html = re.sub(r'href="(\d\d)/(\d\d)"', fr'href="rc://{self.lang_code}/obs-tq/help/\1/\2"', html)

        # Changes references to chapter/frame that are just chapter/frame prefixed with a #
        # #1:10 => <a href="rc://en/obs/book/obs/01/10">01:10</a>
        # #10/1 => <a href="rc://en/obs/book/obs/10/01">10:01</a>
        # #10/12 => <a href="rc://en/obs/book/obs/10/12">10:12</a>
        html = re.sub(r'#(\d)[:/-](\d+)', r'#0\1-\2', html)  # prefix 0 on single-digit chapters
        html = re.sub(r'#(\d+)[:/-](\d)\b', r'#\1-0\2', html)  # prefix 0 on single-digit frames
        html = re.sub(r'#(\d\d)[:/-](\d\d)', rf'<a href="rc://{self.lang_code}/obs-tq/help/\1/\2">\1:\2</a>', html)

        return html
