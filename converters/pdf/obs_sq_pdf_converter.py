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
from door43_tools.subjects import OBS_STUDY_QUESTIONS
from glob import glob
from bs4 import BeautifulSoup
from general_tools import obs_tools
from .obs_sn_pdf_converter import ObsSnPdfConverter


class ObsSqPdfConverter(ObsSnPdfConverter):
    my_subject = OBS_STUDY_QUESTIONS

    def get_sample_text(self):
        md_file = os.path.join(self.main_resource.repo_dir, 'content', '01.md')
        html = markdown2.markdown_path(md_file)
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

    def get_body_html(self):
        obs_sq_html = f'''
<section id="{self.lang_code}-obs-sq">
    <div class="resource-title-page">
        <img src="{self.resources[f'obs-sq'].logo_url}" class="logo" alt="OBS">
        <h1 class="section-header">{self.simple_title}</h1>
    </div>
'''
        files = sorted(glob(os.path.join(self.main_resource.repo_dir, 'content', '*.md')))
        for file in files:
            chapter_num = os.path.splitext(os.path.basename(file))[0]
            chapter_html = markdown2.markdown_path(file)
            chapter_html = html_tools.increment_headers(chapter_html)
            soup = BeautifulSoup(chapter_html, 'html.parser')
            headers = soup.find_all(re.compile(r'^h\d'))
            top_header = headers[0]
            title = top_header.text
            header_count = 1
            for header in headers:
                header['class'] = 'section-header'
                header['id'] = f'{self.lang_code}-obs-sq-{chapter_num}-{header_count}'
                header_count += 1
            # HANDLE OBS SQ RC CHAPTER LINKS
            obs_sq_rc_link = f'rc://{self.lang_code}/obs-sq/help/{chapter_num}'
            obs_sq_rc = self.add_rc(obs_sq_rc_link, title=title, article=chapter_html)
            chapter_data = obs_tools.get_obs_chapter_data(self.resources['obs'].repo_dir, chapter_num)
            if len(chapter_data['frames']):
                frames_html = '<div class="obs-frames">\n'
                for idx, frame in enumerate(chapter_data['frames']):
                    frame_num = str(idx+1).zfill(2)
                    frame_title = f'{chapter_num}:{frame_num}'
                    # HANDLE FRAME RC LINKS FOR OBS
                    frame_rc_link = f'rc://{self.lang_code}/obs/book/obs/{chapter_num}/{frame_num}'
                    frame_rc = self.add_rc(frame_rc_link, title=frame_title)
                    frames_html += f'''
    <div id={frame_rc.article_id} class="obs-frame">
        <div class="obs-frame-title">
            {frame_title}
        </div>
        <div class="obs-frame-text">
            {frame['text']}
        </div>
    </div>
'''
                frames_html += '</div>\n'
                top_header.insert_after(BeautifulSoup(frames_html, 'html.parser'))
                bible_reference_html = f'''
    <div class="bible-reference">
        {chapter_data['bible_reference']}
    </div>
'''
                top_header.insert_after(BeautifulSoup(bible_reference_html, 'html.parser'))

            article_html = f'''
    <article id="{obs_sq_rc.article_id}">
        {str(soup)}
    </article>
'''
            obs_sq_html += article_html
        return obs_sq_html
