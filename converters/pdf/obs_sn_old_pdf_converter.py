#!/usr/bin/env python3
#
#  Copyright (c) 2020 unfoldingWord
#  http://creativecommons.org/licenses/MIT/
#  See LICENSE file for details.
#
#  Contributors:
#  Richard Mahn <rich.mahn@unfoldingword.org>

"""
This script generates the HTML and PDF OBS SN documents
"""
import os
import markdown
import general_tools.html_tools as html_tools
from door43_tools.subjects import OBS_STUDY_NOTES
from obs_sn_pdf_converter import ObsSnPdfConverter
from general_tools import obs_tools, alignment_tools
from bs4 import BeautifulSoup


class ObsSnPdfConverter(ObsSnPdfConverter):
    my_subject = OBS_STUDY_NOTES

    def get_sample_text(self):
        md_file = os.path.join(self.main_resource.repo_dir, 'content', '01', '01.md')
        with open(md_file, "r", encoding="utf-8") as input_file:
            markdown_text = input_file.read()
        html = markdown.markdown(markdown_text, extensions=['md_in_html', 'tables', 'footnotes'])
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
        self.log.info('Generating OBS SN html...')
        obs_sn_html = f'''
<section id="{self.language_id}-obs-sn">
    <div class="resource-title-page no-header">
        <img src="{self.resources[f'obs-sn'].logo_url}" class="logo" alt="OBS">
        <h1 class="section-header">{self.simple_title}</h1>
    </div>
'''
        for chapter in range(1, 51):
            chapter_num = str(chapter).zfill(2)
            sn_chapter_dir = os.path.join(self.resources[f'obs-sn'].repo_dir, 'content', chapter_num)
            chapter_data = obs_tools.get_obs_chapter_data(self.resources['obs'].repo_dir, chapter_num)
            obs_sn_html += f'<article id="{self.language_id}-obs-sn-{chapter_num}">\n\n'
            obs_sn_html += f'<h2 class="section-header">{chapter_data["title"]}</h2>\n'
            if 'bible_reference' in chapter_data and chapter_data['bible_reference']:
                obs_sn_html += f'''
                    <div class="bible-reference no-break">{chapter_data['bible_reference']}</div>
'''
            for frame_idx, frame in enumerate(chapter_data['frames']):
                frame_num = str(frame_idx+1).zfill(2)
                frame_title = f'{chapter_num}:{frame_num}'
                obs_sn_file = os.path.join(sn_chapter_dir, f'{frame_num}.md')

                if os.path.isfile(obs_sn_file):
                    with open(obs_sn_file, "r", encoding="utf-8") as input_file:
                        markdown_text = input_file.read()
                    notes_html = markdown.markdown(markdown_text, extensions=['md_in_html', 'tables', 'footnotes'])
                    notes_html = html_tools.increment_headers(notes_html, 3)
                else:
                    no_study_notes = self.translate('no_study_notes_for_this_frame')
                    notes_html = f'<div class="no-notes-message">({no_study_notes})</div>'

                # HANDLE RC LINKS FOR OBS SN FRAMES
                obs_sn_rc_link = f'rc://{self.language_id}/obs-sn/help/obs/{chapter_num}/{frame_num}'
                obs_sn_rc = self.add_rc(obs_sn_rc_link, title=frame_title, article=notes_html)
                # HANDLE RC LINKS FOR OBS FRAMES
                obs_rc_link = f'rc://{self.language_id}/obs/bible/obs/{chapter_num}/{frame_num}'
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
