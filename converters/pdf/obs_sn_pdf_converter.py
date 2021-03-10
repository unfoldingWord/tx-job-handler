#!/usr/bin/env python3
#
#  Copyright (c) 2020 unfoldingWord
#  http://creativecommons.org/licenses/MIT/
#  See LICENSE file for details.
#
#  Contributors:
#  Richard Mahn <rich.mahn@unfoldingword.org>

"""
This script generates the HTML and PDF OBS SN & SQ documents
"""
import os
import re
import markdown2
import general_tools.html_tools as html_tools
from door43_tools.subjects import OBS_STUDY_NOTES
from bs4 import BeautifulSoup
from .pdf_converter import PdfConverter
from general_tools import obs_tools, alignment_tools


class ObsSnPdfConverter(PdfConverter):
    my_subject = OBS_STUDY_NOTES

    def get_sample_text(self):
        first_frame = os.path.join(self.main_resource.repo_dir, 'content', '01', '01.md')
        html = markdown2.markdown_path(first_frame)
        soup = BeautifulSoup(html, 'html.parser')
        return soup.find('p').text

    @property
    def name(self):
        return 'obs-sn-sq'

    @property
    def file_project_and_ref(self):
        sn_ref = self.main_resource.version
        if self.project_id == 'obs-sn-sq':
            sq_ref = self.resources['obs-sq'].version
            ref = f'v{sn_ref}-v{sq_ref}'
        else:
            ref = f'v{sn_ref}'
        return f'{self.file_project_id}_{ref}'

    @property
    def title(self):
        sn_title = self.resources[f'obs-sn'].title
        if self.project_id == 'obs-sn-sq':
            sq_title = self.resources[f'obs-sq'].title
            return f'{sn_title}\n<br/>\n&\n<br/>\n{sq_title}'
        else:
            return sn_title

    @property
    def simple_title(self):
        sn_title = self.resources[f'obs-sn'].simple_title
        if self.project_id == 'obs-sn-sq':
            sq_title = self.resources[f'obs-sq'].simple_title
            return f'{sn_title} & {sq_title}'
        else:
            return sn_title

    @property
    def project_title(self):
        return ''

    @property
    def file_project_id(self):
        return f'{self.lang_code}_{self.project_id}'

    def generate_all_files(self):
        for project in ['obs-sn', 'obs-sn-sq']:
            self.project_id = project
            self.errors = {}
            self.bad_highlights = {}
            self.rcs = {}
            self.appendix_rcs = {}
            self.all_rcs = {}
            self.generate_html_file()
            self.generate_pdf_file()

    def get_body_html(self):
        if self.project_id == 'obs-sn-sq':
            return self.get_obs_sn_sq_body_html()
        else:
            return self.get_obs_sn_body_html()

    def get_obs_sn_body_html(self):
        self.log.info('Generating OBS SN html...')
        obs_sn_html = f'''
        <section id="{self.lang_code}-obs-sn">
            <div class="resource-title-page no-header">
                <img src="{self.resources[f'obs-sn'].logo_url}" class="logo" alt="OBS">
                <h1 class="section-header">{self.simple_title}</h1>
            </div>
        '''
        for chapter in range(1, 51):
            chapter_num = str(chapter).zfill(2)
            sn_chapter_dir = os.path.join(self.resources[f'obs-sn'].repo_dir, 'content', chapter_num)
            chapter_data = obs_tools.get_obs_chapter_data(self.resources['obs'].repo_dir, chapter_num)
            obs_sn_html += f'<article id="{self.lang_code}-obs-sn-{chapter_num}">\n\n'
            obs_sn_html += f'<h2 class="section-header">{chapter_data["title"]}</h2>\n'
            if 'bible_reference' in chapter_data and chapter_data['bible_reference']:
                obs_sn_html += f'''
                            <div class="bible-reference no-break">{chapter_data['bible_reference']}</div>
        '''
            for frame_idx, frame in enumerate(chapter_data['frames']):
                frame_num = str(frame_idx + 1).zfill(2)
                frame_title = f'{chapter_num}:{frame_num}'
                obs_sn_file = os.path.join(sn_chapter_dir, f'{frame_num}.md')

                if os.path.isfile(obs_sn_file):
                    notes_html = markdown2.markdown_path(obs_sn_file)
                    notes_html = html_tools.increment_headers(notes_html, 3)
                else:
                    no_study_notes = self.translate('no_study_notes_for_this_frame')
                    notes_html = f'<div class="no-notes-message">({no_study_notes})</div>'

                # HANDLE RC LINKS FOR OBS SN FRAMES
                obs_sn_rc_link = f'rc://{self.lang_code}/obs-sn/help/obs/{chapter_num}/{frame_num}'
                obs_sn_rc = self.add_rc(obs_sn_rc_link, title=frame_title, article=notes_html)
                # HANDLE RC LINKS FOR OBS FRAMES
                obs_rc_link = f'rc://{self.lang_code}/obs/bible/obs/{chapter_num}/{frame_num}'
                self.add_rc(obs_rc_link, title=frame_title, article_id=obs_sn_rc.article_id)

                obs_text = ''
                if frame['text'] and notes_html:
                    obs_text = frame['text']
                    orig_obs_text = obs_text
                    phrases = html_tools.get_phrases_to_highlight(notes_html, 'h4')
                    if phrases:
                        for phrase in phrases:
                            alignment = alignment_tools.split_string_into_alignment(phrase)
                            marked_obs_text = html_tools.mark_phrases_in_html(obs_text, alignment)
                            if not marked_obs_text:
                                self.add_bad_highlight(obs_sn_rc, orig_obs_text, obs_sn_rc.rc_link, phrase)
                            else:
                                obs_text = marked_obs_text

                obs_sn_html += f'''
        <div id="{obs_sn_rc.article_id}" class="frame">
            <h3>{frame_title}</h3>
            <div id="{obs_sn_rc.article_id}-text" class="frame-text">
                {obs_text}
            </div>
            <div id="{obs_sn_rc.article_id}-notes" class="frame-notes">
                {notes_html}
            </div>
        </div>
        '''
                if frame_idx < len(chapter_data['frames']) - 1:
                    obs_sn_html += '<hr class="frame-divider"/>'
            obs_sn_html += '</article>\n\n'
        obs_sn_html += '</section>'
        return obs_sn_html

    def get_obs_sn_sq_body_html(self):
        self.log.info('Generating OBS SN SQ html...')
        obs_sn_sq_html = f'''
<section id="{self.lang_code}-obs-sn">
    <div class="resource-title-page no-header">
        <img src="{self.resources[f'obs-sn'].logo_url}" class="logo" alt="OBS">
        <h1 class="section-header">{self.simple_title}</h1>
    </div>
'''
        intro_file = os.path.join(self.resources[f'obs-sq'].repo_dir, 'content', '00.md')
        if os.path.isfile(intro_file):
            intro_id = 'obs-sq-intro'
            intro_content = markdown2.markdown_path(intro_file)
            intro_content = html_tools.increment_headers(intro_content, 1)
            intro_content = intro_content.replace('<h2>', '<h2 class="section-header">', 1)
            obs_sn_sq_html += f'''
    <article id="{intro_id}">
        {intro_content}
    </article>
'''
        for chapter_num in range(1, 51):
            chapter_num = str(chapter_num).zfill(2)
            sn_chapter_dir = os.path.join(self.resources[f'obs-sn'].repo_dir, 'content', chapter_num)
            sq_chapter_file = os.path.join(self.resources[f'obs-sq'].repo_dir, 'content', f'{chapter_num}.md')
            obs_chapter_data = obs_tools.get_obs_chapter_data(self.resources['obs'].repo_dir, chapter_num)
            chapter_title = obs_chapter_data['title']
            # HANDLE RC LINKS FOR OBS SN CHAPTER
            obs_sn_chapter_rc_link = f'rc://{self.lang_code}/obs-sn/help/obs/{chapter_num}'
            obs_sn_chapter_rc = self.add_rc(obs_sn_chapter_rc_link, title=chapter_title)
            obs_sn_sq_html += f'''
    <section id="{obs_sn_chapter_rc.article_id}">
        <h2 class="section-header">{chapter_title}</h2>
        <section id="{obs_sn_chapter_rc.article_id}-notes" class="no-break">
            <h3 class="section-header no-break">{self.translate('study_notes')}</h3>
'''
            if 'bible_reference' in obs_chapter_data and obs_chapter_data['bible_reference']:
                obs_sn_sq_html += f'''
                    <div class="bible-reference" class="no-break">{obs_chapter_data['bible_reference']}</div>
            '''
            frames = obs_chapter_data['frames']
            for frame_idx, frame in enumerate(frames):
                image = frame['image']
                frame_num = str(frame_idx + 1).zfill(2)
                frame_title = f'{chapter_num}:{frame_num}'
                obs_sn_file = os.path.join(sn_chapter_dir, f'{frame_num}.md')

                if os.path.isfile(obs_sn_file):
                    notes_html = markdown2.markdown_path(obs_sn_file)
                    notes_html = html_tools.increment_headers(notes_html, 3)
                else:
                    no_study_notes = self.translate('no_study_notes_for_this_frame')
                    notes_html = f'<div class="no-notes-message">({no_study_notes})</div>'

                # HANDLE RC LINKS FOR OBS SN FRAME
                obs_sn_rc_link = f'rc://{self.lang_code}/obs-sn/help/obs/{chapter_num}/{frame_num}'
                obs_sn_rc = self.add_rc(obs_sn_rc_link, title=frame_title, article=notes_html)
                # HANDLE RC LINKS FOR OBS FRAME
                obs_rc_link = f'rc://{self.lang_code}/obs/book/obs/{chapter_num}/{frame_num}'
                self.add_rc(obs_rc_link, title=frame_title, article_id=obs_sn_rc.article_id)

                obs_text = ''
                if frame['text'] and notes_html:
                    obs_text = frame['text']
                    orig_obs_text = obs_text
                    phrases = html_tools.get_phrases_to_highlight(notes_html, 'h4')
                    if phrases:
                        for phrase in phrases:
                            alignment = alignment_tools.split_string_into_alignment(phrase)
                            marked_obs_text = html_tools.mark_phrases_in_html(obs_text, alignment)
                            if not marked_obs_text:
                                self.add_bad_highlight(obs_sn_rc, orig_obs_text, obs_sn_rc.rc_link, phrase)
                            else:
                                obs_text = marked_obs_text

                obs_sn_sq_html += f'''
        <article id="{obs_sn_rc.article_id}">
          <h4>{frame_title}</h4>
          <div class="obs-img-and-text">
            <img src="{image}" class="obs-img"/>
            <div class="obs-text">
                {obs_text}
            </div>
          </div>
          <div class="obs-sn-notes">
            {notes_html}
          </div>
        </article>
'''
            obs_sn_sq_html += '''
    </section>
'''
            if os.path.isfile(sq_chapter_file):
                obs_sq_title = f'{self.translate("study_questions")}'
                obs_sq_html = markdown2.markdown_path(sq_chapter_file)
                obs_sq_html = html_tools.increment_headers(obs_sq_html, 2)
                soup = BeautifulSoup(obs_sq_html, 'html.parser')
                header = soup.find(re.compile(r'^h\d'))
                header.decompose()
                obs_sq_html = str(soup)
                # HANDLE RC LINKS FOR OBS SQ
                obs_sq_rc_link = f'rc://{self.lang_code}/obs-sq/help/obs/{chapter_num}'
                obs_sq_rc = self.add_rc(obs_sq_rc_link, title=obs_sq_title, article=obs_sq_html)
                obs_sn_sq_html += f'''
        <article id="{obs_sq_rc.article_id}">
          <h3 class="section-header">{obs_sq_title}</h3>
          {obs_sq_html}
        </article>
    </section>
'''
        obs_sn_sq_html += '''
</section>
'''
        return obs_sn_sq_html

    def fix_links(self, html):
        # Changes references to chapter/frame in links
        # <a href="1/10">Text</a> => <a href="rc://obs-sn/help/obs/01/10">Text</a>
        # <a href="10-1">Text</a> => <a href="rc://obs-sn/help/obs/10/01">Text</a>
        html = re.sub(r'href="(\d)/(\d+)"', r'href="0\1/\2"', html)  # prefix 0 on single-digit chapters
        html = re.sub(r'href="(\d+)/(\d)"', r'href="\1/0\2"', html)  # prefix 0 on single-digit frames
        html = re.sub(r'href="(\d\d)/(\d\d)"', fr'href="rc://{self.lang_code}/obs/book/obs/\1/\2"', html)

        # Changes references to chapter/frame that are just chapter/frame prefixed with a #
        # #1:10 => <a href="rc://en/obs/book/obs/01/10">01:10</a>
        # #10/1 => <a href="rc://en/obs/book/obs/10/01">10:01</a>
        # #10/12 => <a href="rc://en/obs/book/obs/10/12">10:12</a>
        html = re.sub(r'#(\d)[:/-](\d+)', r'#0\1-\2', html)  # prefix 0 on single-digit chapters
        html = re.sub(r'#(\d+)[:/-](\d)\b', r'#\1-0\2', html)  # prefix 0 on single-digit frames
        html = re.sub(r'#(\d\d)[:/-](\d\d)', rf'<a href="rc://{self.lang_code}/obs/book/obs/\1/\2">\1:\2</a>', html)

        return html
