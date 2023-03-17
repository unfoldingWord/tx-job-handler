#!/usr/bin/env python3
#
#  Copyright (c) 2020 unfoldingWord
#  http://creativecommons.org/licenses/MIT/
#  See LICENSE file for details.
#
#  Contributors:
#  Richard Mahn <rich.mahn@unfoldingword.org>

"""
This script generates the HTML and PDF OBS TN & TQ documents
"""
import os
import re
import csv
import markdown2
import general_tools.html_tools as html_tools
from door43_tools.subjects import TSV_OBS_TRANSLATION_NOTES
from bs4 import BeautifulSoup
from .pdf_converter import PdfConverter
from general_tools import obs_tools, alignment_tools
from general_tools.url_utils import download_file
from general_tools.file_utils import unzip


class ObsTnTsvToPdfConverter(PdfConverter):
    my_subject = TSV_OBS_TRANSLATION_NOTES

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.tn_data = {}
        self.tq_data = {}
        self.twl_data = {}

    def reinit(self):
        super().reinit()
        self.tn_data = {}
        self.tq_data = {}
        self.twl_data = {}

    def get_default_project_ids(self):
        return ["obs-tn", "obs-bp"]
    
    def get_sample_text(self):
        first_frame = os.path.join(self.main_resource.repo_dir, 'content', '01', '01.md')
        html = markdown2.markdown_path(first_frame)
        soup = BeautifulSoup(html, 'html.parser')
        return soup.find('p').text

    @property
    def name(self):
        return self.project_id if self.project_id else "obs-tn"

    @property
    def version(self):
        if self.project_id == "obs-bp":
            return self.resources["obs"].version
        else:
            return self.main_resource.version

    @property
    def file_project_and_ref(self):
        if self.project_id == "obs-bp":
            return f'{self.file_project_id}_v{self.resources["obs"].version}'
        else:
            return f'{self.file_project_id}_{self.ref}'

    @property
    def title(self):
        if self.project_id == 'obs-bp':
            return f'{self.resources["obs"].title}'
        else:
            return self.resources["obs-tn"].title

    @property
    def simple_title(self):
        if self.project_id == 'obs-bp':
            return f'{self.resources["obs"].simple_title} BP'
        else:
            return self.resources["obs-tn"].simple_title

    @property
    def project_title(self):
        if self.project_id == 'obs-bp':
            return 'Book Package\n<br/>\nStories 1 - 50'
        else:
            return ''

    @property
    def file_project_id(self):
        return f'{self.language_id}_{self.main_resource.identifier}'

    @staticmethod
    def unicode_csv_reader(utf8_data, dialect=csv.excel, **kwargs):
        csv_reader = csv.reader(utf8_data, dialect=dialect, delimiter=str("\t"), quotechar=str('"'), **kwargs)
        for row in csv_reader:
            yield [cell for cell in row]

    def setup_images_dir(self):
        super().setup_images_dir()
        jpg_dir = os.path.join(self.images_dir, 'cdn.door43.org', 'obs', 'jpg')
        if not os.path.exists(jpg_dir):
            download_file('http://cdn.door43.org/obs/jpg/obs-images-360px-compressed.zip', os.path.join(self.images_dir,
                                                                                                        'images.zip'))
            unzip(os.path.join(self.images_dir, 'images.zip'), jpg_dir)
            os.unlink(os.path.join(self.images_dir, 'images.zip'))

    def get_tn_data(self):
        book_filepath = os.path.abspath(os.path.join(self.main_resource.repo_dir, "tn_OBS.tsv"))
        if not os.path.isfile(book_filepath):
            print("ERROR: tn_OBS.tsv does not exist!!!")
            exit(1)
        reader = self.unicode_csv_reader(open(book_filepath))
        next(reader)
        for row in reader:
            c, v = row[0].split(':')
            c = c.zfill(2)
            v = v.zfill(2)
            if c not in self.tn_data:
                self.tn_data[c] = {}
            if v not in self.tn_data[c]:
                self.tn_data[c][v] = []
            self.tn_data[c][v].append({
                "ref": row[0],
                "id": row[1],
                "tags": row[2],
                "sr": row[3],
                "quote": row[4],
                "occurrence": row[5],
                "note": row[6]
            })
        
    def get_tq_data(self):
        book_filepath = os.path.abspath(os.path.join(self.resources['obs-tq'].repo_dir, "tq_OBS.tsv"))
        if not os.path.isfile(book_filepath):
            print("ERROR: tq_OBS.tsv does not exist!!!")
            exit(1)
        reader = self.unicode_csv_reader(open(book_filepath))
        next(reader)
        for row in reader:
            c, v = row[0].split(':')
            c = c.zfill(2)
            v = v.zfill(2)
            if c not in self.tq_data:
                self.tq_data[c] = {}
            if v not in self.tq_data[c]:
                self.tq_data[c][v] = []
            self.tq_data[c][v].append({
                "ref": row[0],
                "id": row[1],
                "tags": row[2],
                "quote": row[3],
                "occurrence": row[4],
                "question": row[5],
                "response": row[6]
            })

    def get_twl_data(self):
        book_filepath = os.path.abspath(os.path.join(self.resources['obs-twl'].repo_dir, "twl_OBS.tsv"))
        if not os.path.isfile(book_filepath):
            print("ERROR: twl_OBS.tsv does not exist!!!")
            exit(1)
        reader = self.unicode_csv_reader(open(book_filepath))
        next(reader)
        for row in reader:
            c, v = row[0].split(':')
            c = c.zfill(2)
            v = v.zfill(2)
            if c not in self.twl_data:
                self.twl_data[c] = {}
            if v not in self.twl_data[c]:
                self.twl_data[c][v] = []
            self.twl_data[c][v].append({
                "ref": row[0],
                "id": row[1],
                "tags": row[2],
                "word": row[3],
                "occurrence": row[4],
                "link": row[5]
            })
        
    def get_body_html(self):
        self.get_tn_data()
        if self.project_id == "obs-bp":
            self.get_tq_data()
            self.get_twl_data()
            return self.get_obs_tn_tq_body_html()
        else:
            return self.get_obs_tn_body_html()

    def get_obs_tn_body_html(self):
        self.log.info('Generating OBS TN html...')
        obs_tn_html = f'''
        <section id="{self.language_id}-obs-tn">
            <h1 class="section-header">{self.simple_title}</h1>
        '''
        for chapter in range(1, 51):
            chapter_num = str(chapter).zfill(2)
            chapter_data = obs_tools.get_obs_chapter_data(self.resources['obs'].repo_dir, chapter_num)
            obs_tn_html += f'<article id="{self.language_id}-obs-tn-{chapter_num}">\n\n'
            obs_tn_html += f'<h2 class="section-header">{chapter_data["title"]}</h2>\n'
            if 'bible_reference' in chapter_data and chapter_data['bible_reference']:
                obs_tn_html += f'''
                            <div class="bible-reference no-break">{chapter_data['bible_reference']}</div>
        '''
            if chapter_num in self.tn_data and "00" in self.tn_data[chapter_num]:
                for note in self.tn_data[chapter_num]["00"]:
                    title = note["quote"]
                    body = markdown2.markdown(note["note"])
                    obs_tn_html += f"<h4>{title}</h4>\n{body}\n"
            for frame_idx, frame in enumerate(chapter_data['frames']):
                frame_num = str(frame_idx + 1).zfill(2)
                frame_title = f'{chapter_num}:{frame_num}'
                image = frame['image']

                notes_html = ""
                if chapter_num in self.tn_data and frame_num in self.tn_data[chapter_num]:
                    for note in self.tn_data[chapter_num][frame_num]:
                        title = note["quote"]
                        body = markdown2.markdown(note["note"])
                        notes_html += f"<h5>{title}</h5>\n{markdown2.markdown(body)}\n"
                        if note['sr']:
                            notes_html += f'See TA article: [[{note["sr"]}]]\n'
                else:
                    no_notes = self.translate('no_translation_notes_for_this_frame')
                    notes_html = f'<div class="no-notes-message">({no_notes})</div>'

                # HANDLE RC LINKS FOR OBS TN FRAMES
                obs_tn_rc_link = f'rc://{self.language_id}/obs-tn/help/obs/{chapter_num}/{frame_num}'
                obs_tn_rc = self.add_rc(obs_tn_rc_link, title=frame_title, article=notes_html)
                # HANDLE RC LINKS FOR OBS FRAMES
                obs_rc_link = f'rc://{self.language_id}/obs/bible/obs/{chapter_num}/{frame_num}'
                self.add_rc(obs_rc_link, title=frame_title, article_id=obs_tn_rc.article_id)

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
                                self.add_bad_highlight(obs_tn_rc, orig_obs_text, obs_tn_rc.rc_link, phrase)
                            else:
                                obs_text = marked_obs_text

                obs_tn_html += f'''
        <div id="{obs_tn_rc.article_id}" class="frame">
            <h3>{frame_title}</h3>
            <img src="{image}" class="obs-img"/>
            <div id="{obs_tn_rc.article_id}-text" class="frame-text">
                {obs_text}
            </div>
            <div id="{obs_tn_rc.article_id}-notes" class="frame-notes">
                <h4 id="obs-tn-{chapter_num}-{frame_num}">{self.translate('translation_notes')}</h4>
                <div class="obs-tn-notes-contents contents">
                   {notes_html}
                </div>
            </div>
        </div>
        '''
                if frame_idx < len(chapter_data['frames']) - 1:
                    obs_tn_html += '<hr class="frame-divider"/>'
            obs_tn_html += '</article>\n\n'
        obs_tn_html += '</section>'
        return obs_tn_html

    def get_obs_tn_tq_body_html(self):        
        self.log.info('Generating OBS TN TQ html...')
        obs_tn_tq_html = f'''
<section id="{self.language_id}-obs-tn">
    <h1 class="section-header">{self.simple_title}</h1>
'''
        for chapter in range(1, 51):
            chapter_num = str(chapter).zfill(2)
            chapter_data = obs_tools.get_obs_chapter_data(self.resources['obs'].repo_dir, chapter_num)
            obs_tn_tq_html += f'<article id="{self.language_id}-obs-tn-{chapter_num}">\n\n'
            obs_tn_tq_html += f'<h2 class="section-header">{chapter_data["title"]}</h2>\n'
            if 'bible_reference' in chapter_data and chapter_data['bible_reference']:
                obs_tn_tq_html += f'''
                            <div class="bible-reference no-break">{chapter_data['bible_reference']}</div>
        '''
            if chapter_num in self.tn_data and "00" in self.tn_data[chapter_num]:
                for note in self.tn_data[chapter_num]["00"]:
                    title = note["quote"]
                    body = markdown2.markdown(note["note"])
                    obs_tn_tq_html += f"<h3>{title}</h3>\n{body}\n"
            for frame_idx, frame in enumerate(chapter_data['frames']):
                frame_num = str(frame_idx + 1).zfill(2)
                frame_title = f'{chapter_num}:{frame_num}'
                image = frame['image']

                notes_html = ""
                if chapter_num in self.tn_data and frame_num in self.tn_data[chapter_num]:
                    for note in self.tn_data[chapter_num][frame_num]:
                        title = note["quote"]
                        body = markdown2.markdown(note["note"])
                        notes_html += f"<h5>{title}</h5>\n{markdown2.markdown(body)}\n"
                        if note['sr']:
                            notes_html += f'See TA article: [[{note["sr"]}]]\n'
                else:
                    no_notes = self.translate('no_translation_notes_for_this_frame')
                    notes_html = f'<div class="no-notes-message">({no_notes})</div>'

                if chapter_num in self.twl_data and frame_num in self.twl_data[chapter_num]:
                    words_html = "<ul>\n"
                    for twl in self.twl_data[chapter_num][frame_num]:
                        words_html += f'<li><a class="pageref round black" href="{twl["link"]}">{twl["word"]}</a></li>\n'
                    words_html += "</ul>\n"
                else:
                    no_words = self.translate('no_translation_words_for_this_frame')
                    notes_html = f'<div class="no-words-message">({no_words})</div>'

                questions_html = ""
                if chapter_num in self.tq_data and frame_num in self.tq_data[chapter_num]:
                    for question in self.tq_data[chapter_num][frame_num]:
                        q = markdown2.markdown(question["question"])
                        r = markdown2.markdown(question["response"])
                        questions_html += f'<h5 class="tq-question">{q}</h5>\n<span class="tq-response">{r}</span>\n'
                else:
                    no_questions = self.translate('no_translation_questions_for_this_frame')
                    questions_html = f'<div class="no-questions-message">({no_questions})</div>'

                # HANDLE RC LINKS FOR OBS TN FRAME
                obs_tn_rc_link = f'rc://{self.language_id}/obs-tn/help/obs/{chapter_num}/{frame_num}'
                obs_tn_rc = self.add_rc(obs_tn_rc_link, title=frame_title, article=notes_html + words_html + questions_html)
                # HANDLE RC LINKS FOR OBS FRAME
                obs_rc_link = f'rc://{self.language_id}/obs/book/obs/{chapter_num}/{frame_num}'
                self.add_rc(obs_rc_link, title=frame_title, article_id=obs_tn_rc.article_id)

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
                                self.add_bad_highlight(obs_tn_rc, orig_obs_text, obs_tn_rc.rc_link, phrase)
                            else:
                                obs_text = marked_obs_text

                obs_tn_tq_html += f'''
        <article id="{obs_tn_rc.article_id}">
          <h3>{frame_title}</h3>
          <div class="obs-img-and-text">
            <img src="{image}" class="obs-img"/>
            <div class="obs-text">
                {obs_text}
            </div>
          </div>
          <div class="obs-tn-notes">
            <h4 id="obs-tn-{chapter_num}-{frame_num}">{self.translate('translation_notes')}</h4>
            <div class="obs-tn-notes-contents contents">
               {notes_html}
            </div>
          </div>
          <div class="obs-tw-words">
            <h4 id="obs-tw-{chapter_num}-{frame_num}">{self.translate('translation_words')}</h4>
            <div class="obs-tw-words-contents">
                {words_html}
            </div>
          </div>
          <div class="obs-tq-questions">
            <h4 id="obs-tq-{chapter_num}-{frame_num}">{self.translate('translation_questions')}</h4>
            <div class="obs-tq-questions-contents contents">
                {questions_html}
            </div>
          </div>
        </article>
'''
            obs_tn_tq_html += '''
    </section>
'''
        obs_tn_tq_html += '''
</section>
'''
        return obs_tn_tq_html

    def fix_links(self, html):
        # Changes references to chapter/frame in links
        # <a href="1/10">Text</a> => <a href="rc://obs-tn/help/obs/01/10">Text</a>
        # <a href="10-1">Text</a> => <a href="rc://obs-tn/help/obs/10/01">Text</a>
        html = re.sub(r'href="(\d)/(\d+)"', r'href="0\1/\2"', html)  # prefix 0 on single-digit chapters
        html = re.sub(r'href="(\d+)/(\d)"', r'href="\1/0\2"', html)  # prefix 0 on single-digit frames
        html = re.sub(r'href="(\d\d)/(\d\d)"', fr'href="rc://{self.language_id}/obs/book/obs/\1/\2"', html)

        # Changes references to chapter/frame that are just chapter/frame prefixed with a #
        # #1:10 => <a href="rc://en/obs/book/obs/01/10">01:10</a>
        # #10/1 => <a href="rc://en/obs/book/obs/10/01">10:01</a>
        # #10/12 => <a href="rc://en/obs/book/obs/10/12">10:12</a>
        html = re.sub(r'#(\d)[:/-](\d+)', r'#0\1-\2', html)  # prefix 0 on single-digit chapters
        html = re.sub(r'#(\d+)[:/-](\d)\b', r'#\1-0\2', html)  # prefix 0 on single-digit frames
        html = re.sub(r'#(\d\d)[:/-](\d\d)', rf'<a href="rc://{self.language_id}/obs/book/obs/\1/\2">\1:\2</a>', html)

        return html
