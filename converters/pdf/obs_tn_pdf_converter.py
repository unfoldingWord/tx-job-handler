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
import markdown
from bs4 import BeautifulSoup
from door43_tools.subjects import OBS_TRANSLATION_NOTES
from glob import glob
from .tsv_pdf_converter import TsvPdfConverter
from general_tools.file_utils import load_json_object
from general_tools import obs_tools, html_tools, alignment_tools
from general_tools.url_utils import get_url, download_file
from general_tools.file_utils import unzip

# Enter ignores in lowercase
TN_TITLES_TO_IGNORE = {
    'en': ['a bible story from',
           'connecting statement',
           'connecting statement:',
           'general information',
           'general note'
           ],
    'fr': ['information générale',
           'termes importants',
           'une histoire biblique tirée de',
           'une histoire de la bible tirée de',
           'une histoire de la bible à partir',
           'une histoire de la bible à partir de',
           'mots de traduction',
           'nota geral',
           'déclaration de connexion',
           'cette histoire biblique est tirée',
           'une histoire biblique tirée de:',
           'informations générales'
           ]
}


class ObsTnPdfConverter(TsvPdfConverter):
    my_subject = OBS_TRANSLATION_NOTES

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._tw_cat = None
        self.bad_notes = {}

    def setup_images_dir(self):
        super().setup_images_dir()
        jpg_dir = os.path.join(self.images_dir, 'cdn.door43.org', 'obs', 'jpg')
        if not os.path.exists(jpg_dir):
            download_file('http://cdn.door43.org/obs/jpg/obs-images-360px-compressed.zip', os.path.join(self.images_dir,
                                                                                                        'images.zip'))
            unzip(os.path.join(self.images_dir, 'images.zip'), jpg_dir)
            os.unlink(os.path.join(self.images_dir, 'images.zip'))

    @property
    def tw_cat(self):
        if not self._tw_cat:
            mapping = {
                'idol': 'falsegod',
                'witness': 'testimony',
                'newcovenant': 'covenant',
                'taxcollector': 'tax',
                'believer': 'believe'
            }
            tw_cat_file = os.path.join(self.pdf_converters_dir, 'tw_cat.json')
            self._tw_cat = load_json_object(tw_cat_file)
            for chapter in self._tw_cat['chapters']:
                self._tw_cat[chapter['id']] = {}
                for frame in chapter['frames']:
                    self._tw_cat[chapter['id']][frame['id']] = []
                    for item in frame['items']:
                        term = item['id']
                        category = None
                        for c in ['kt', 'names', 'other']:
                            if os.path.exists(os.path.join(self.resources['tw'].repo_dir, 'bible', c, f'{term}.md')):
                                category = c
                                break
                        if not category and term in mapping:
                            category = None
                            for c in ['kt', 'names', 'other']:
                                if os.path.exists(os.path.join(self.resources['tw'].repo_dir, 'bible', c,
                                                               f'{mapping[term]}.md')):
                                    category = c
                                    term = mapping[term]
                                    break
                        if category:
                            self._tw_cat[chapter['id']][frame['id']].append(
                                f'rc://{self.language_id}/tw/dict/bible/{category}/{term}')
                        if not category or term != item['id']:
                            fix = None
                            if term != item['id']:
                                fix = f'change to: {term}'
                            source_rc_link = f'rc://{self.language_id}/tw_cat/{chapter["id"]}/{frame["id"]}'
                            source_rc = self.create_rc(source_rc_link)
                            self.add_error_message(source_rc, item['id'], fix)
        return self._tw_cat

    def get_sample_text(self):
        first_frame = os.path.join(self.main_resource.repo_dir, 'content', '01', '01.md')
        with open(first_frame, "r", encoding="utf-8") as input_file:
            markdown_text = input_file.read()
        html = markdown.markdown(markdown_text, extensions=['md_in_html', 'tables', 'footnotes'])
        soup = BeautifulSoup(html, 'html.parser')
        return soup.find('p').text

    def get_body_html(self):
        self.log.info('Generating OBS TN html...')
        return self.get_obs_tn_html()

    def get_obs_tn_html(self):
        obs_tn_html = f'''
<section id="obs-sn">
    <h1 class="section-header">{self.simple_title}</h1>
'''
        obs_tn_chapter_dirs = sorted(glob(os.path.join(self.main_resource.repo_dir, 'content', '*')))
        for obs_tn_chapter_dir in obs_tn_chapter_dirs:
            if os.path.isdir(obs_tn_chapter_dir):
                chapter_num = os.path.basename(obs_tn_chapter_dir)
                chapter_data = obs_tools.get_obs_chapter_data(self.resources['obs'].repo_dir, chapter_num)
                obs_tn_html += f'''
    <section id="{self.language_id}-obs-tn-{chapter_num}">
        <h2 class="section-header">{chapter_data['title']}</h2>
'''
                frames = [None] + chapter_data['frames']  # first item of '' if there are intro notes from the 00.md file
                for frame_idx, frame in enumerate(frames):
                    frame_num = str(frame_idx).zfill(2)
                    frame_title = f'{chapter_num}:{frame_num}'
                    notes_file = os.path.join(obs_tn_chapter_dir, f'{frame_num}.md')
                    notes_html = ''
                    if os.path.isfile(notes_file):
                        with open(notes_file, "r", encoding="utf-8") as input_file:
                            markdown_text = input_file.read()
                        notes_html = markdown.markdown(markdown_text, extensions=['md_in_html', 'tables', 'footnotes'])
                        notes_html = html_tools.increment_headers(notes_html, 3)
                    if (not frame or not frame['text']) and not notes_html:
                        continue

                    # HANDLE RC LINKS FOR OBS FRAME
                    frame_rc_link = f'rc://{self.language_id}/obs/book/obs/{chapter_num}/{frame_num}'
                    frame_rc = self.add_rc(frame_rc_link, title=frame_title)
                    # HANDLE RC LINKS FOR NOTES
                    notes_rc_link = f'rc://{self.language_id}/obs-tn/help/{chapter_num}/{frame_num}'
                    notes_rc = self.add_rc(notes_rc_link, title=frame_title, article=notes_html)

                    obs_text = ''
                    if frame and frame['text']:
                        image = frame['image']
                        obs_text = frame['text']
                        orig_obs_text = obs_text
                        if notes_html:
                            phrases = html_tools.get_phrases_to_highlight(notes_html, 'h4')
                            for phrase in phrases:
                                alignment = alignment_tools.split_string_into_alignment(phrase)
                                marked_obs_text = html_tools.mark_phrases_in_html(obs_text, alignment)
                                if not marked_obs_text:
                                    if self.language_id in TN_TITLES_TO_IGNORE and \
                                            phrase.lower() not in TN_TITLES_TO_IGNORE[self.language_id]:
                                        self.add_bad_highlight(notes_rc, orig_obs_text, notes_rc.rc_link, phrase)
                                else:
                                    obs_text = marked_obs_text

                    if frame_idx == len(frames) - 1:
                        if 'bible_reference' in chapter_data and chapter_data['bible_reference']:
                            notes_html += f'''
                                <div class="bible-reference" class="no-break">{chapter_data['bible_reference']}</div>
                        '''
                    # Some OBS TN languages (e.g. English) do not have Translation Words in their TN article
                    # while some do (e.g. French). We need to add them ourselves from the tw_cat file
                    if notes_html and '/tw/' not in notes_html and chapter_num in self.tw_cat and \
                            frame_num in self.tw_cat[chapter_num] and len(self.tw_cat[chapter_num][frame_num]):
                        notes_html += f'''
           <h3>{self.resources['tw'].simple_title}</h3>
           <ul>
'''
                        for rc_link in self.tw_cat[chapter_num][frame_num]:
                            notes_html += f'''
                <li>[[{rc_link}]]</li>
'''
                        notes_html += '''
            </ul>
'''
                    notes_rc.set_article(notes_html)

                    if obs_text:
                        obs_text = f'''
            <div class="obs-img-and-text">
                <img src="{image}" class="obs-img"/>
                 <div class="obs-text">
                    {obs_text}
                </div>
            </div>
'''
                    if notes_html:
                        notes_html = f'''
            <div id="{notes_rc.article_id}-notes" class="frame-notes">
                {notes_html}
            </div>
'''

                    obs_tn_html += f'''
        <article id="{notes_rc.article_id}">
            <h3>{frame_title}</h3>
            {obs_text}
            {notes_html}
        </article>
'''
                obs_tn_html += '''
    </section>
'''
        obs_tn_html += '''
</section>
'''
        return obs_tn_html

    def fix_links(self, html):
        # Changes references to chapter/frame in links
        # <a href="1/10">Text</a> => <a href="rc://obs-sn/help/obs/01/10">Text</a>
        # <a href="10-1">Text</a> => <a href="rc://obs-sn/help/obs/10/01">Text</a>
        html = re.sub(r'href="(\d)/(\d+)"', r'href="0\1/\2"', html)  # prefix 0 on single-digit chapters
        html = re.sub(r'href="(\d+)/(\d)"', r'href="\1/0\2"', html)  # prefix 0 on single-digit frames
        html = re.sub(r'href="(\d\d)/(\d\d)"', fr'href="rc://{self.language_id}/obs-tn/help/\1/\2"', html)

        # Changes references to chapter/frame that are just chapter/frame prefixed with a #
        # #1:10 => <a href="rc://en/obs/book/obs/01/10">01:10</a>
        # #10/1 => <a href="rc://en/obs/book/obs/10/01">10:01</a>
        # #10/12 => <a href="rc://en/obs/book/obs/10/12">10:12</a>
        html = re.sub(r'#(\d)[:/-](\d+)', r'#0\1-\2', html)  # prefix 0 on single-digit chapters
        html = re.sub(r'#(\d+)[:/-](\d)\b', r'#\1-0\2', html)  # prefix 0 on single-digit frames
        html = re.sub(r'#(\d\d)[:/-](\d\d)', rf'<a href="rc://{self.language_id}/obs-tn/help/\1/\2">\1:\2</a>', html)

        return html
