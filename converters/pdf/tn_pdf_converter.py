#!/usr/bin/env python3
#
#  Copyright (c) 2020 unfoldingWord
#  http://creativecommons.org/licenses/MIT/
#  See LICENSE file for details.
#
#  Contributors:
#  Richard Mahn <rich.mahn@unfoldingword.org>

"""
This script generates the HTML and PDF TN documents
"""
import os
import re
import csv
import markdown
import subprocess
import general_tools.html_tools as html_tools
from door43_tools.subjects import TSV_TRANSLATION_NOTES, ALIGNED_BIBLE
from glob import glob
from collections import OrderedDict
from .pdf_converter import PdfConverter
from .pdf_converter import represent_int
from door43_tools.bible_books import BOOK_CHAPTER_VERSES, BOOK_NUMBERS
from general_tools.alignment_tools import flatten_alignment
from general_tools.file_utils import load_json_object, get_latest_version_path, get_child_directories
from typing import Dict, Optional, List, Any
from bs4 import BeautifulSoup

QUOTES_TO_IGNORE = ['general information:', 'connecting statement:']


class TnPdfConverter(PdfConverter):
    my_subject = TSV_TRANSLATION_NOTES

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    @staticmethod
    def unicode_csv_reader(utf8_data, dialect=csv.excel, **kwargs):
        csv_reader = csv.reader(utf8_data, dialect=dialect, delimiter=str("\t"), quotechar=str('"'), **kwargs)
        for row in csv_reader:
            yield [cell for cell in row]

    def reinit(self):
        super().reinit()
        self.tw_words_data = {}
        self.tn_groups_data = {}
        self.tn_book_data = {}

    def get_sample_text(self):
        project = self.projects[0]
        book_filepath = os.path.abspath(os.path.join(self.main_resource.repo_dir, project['path']))
        if not os.path.isfile(book_filepath):
            return ''
        reader = self.unicode_csv_reader(open(book_filepath))
        next(reader)
        row = next(reader)
        html = markdown.markdown(row[-1].replace('<br>', '\n').replace('<br/>', '\n').replace('<br />', '\n').replace('</br>', '').replace('\\n', "\n"), extensions=['md_in_html', 'tables', 'footnotes'])
        soup = BeautifulSoup(html, 'html.parser')
        p = soup.find('p')
        if not p:
            p = soup
        return p.text

    def get_body_html(self):
        self.log.info('Creating TN for {0}...'.format(self.file_project_and_ref))
        self.populate_tn_book_data()
        html = self.get_tn_html()
        return html

    def determine_ult_bible(self):
        ult_bible = None
        for resource in self.resources.values():
            if resource.subject == ALIGNED_BIBLE:
                if resource.identifier == 'ult' or resource.identifier == 'ulb' or resource.identifier == 'glt':
                    ult_bible = resource
                elif not ult_bible:
                    ult_bible = resource
        if not ult_bible:
            self.log.error('No ULT or similar aligned Bible found. Add one to the relation field in manifest.yaml')
            exit(1)
        return ult_bible

    def add_gl_quotes_to_tsv(self, tsv_filepath: str) -> None:
        bible = self.determine_ult_bible()
        bible_book_filename = f"{self.book_number_padded}-{self.project_id.upper()}" + ".usfm"
        args = ['node', 'add_gl_quotes_to_tsv.js',
                '--source_path', os.path.join(self.download_dir, "el-x-koine_ugnt" if self.book_number >= 40 else "hbo_uhb", bible_book_filename),
                '--target_path', os.path.join(self.download_dir, bible.repo_name, bible_book_filename),
                '--tn_path', tsv_filepath,
               ]
        cmd = ' '.join(args)
        self.log.info(f'Running `{cmd}` in add_gl_quote_to_tsv')
        ret = subprocess.call(cmd, shell=True, cwd=os.path.join(os.path.dirname(os.path.realpath(__file__)), '..', 'add_gl_quotes_to_tsv'), timeout=36000)
        if ret:
            self.log.error('Error running add_gl_quote_to_tsv/add_gl_quote_to_tsv.js. Exiting.')

    def populate_tn_book_data(self):
        tsv_filepath = f'tn_{self.project_id.upper()}.tsv'
        tsv_filepath = os.path.join(self.main_resource.repo_dir, tsv_filepath)
        if not os.path.isfile(tsv_filepath):
            return
        self.add_gl_quotes_to_tsv(tsv_filepath)
        tsv_filepath += ".new"
        book_data = OrderedDict()
        reader = self.unicode_csv_reader(open(tsv_filepath))
        header = next(reader)
        row_count = 1
        for row in reader:
            row_count += 1
            verse_data = {
                'contextId': None,
                'row': row_count,
            }
            found = False
            for idx, field in enumerate(header):
                field = field.strip()
                if idx >= len(row):
                    self.log.error(f'ERROR: {tsv_filepath} is malformed at row {row_count}: {row}')
                    self.add_error_message(self.create_rc(f'{tsv_filepath}#{row_count}'), f'Line {row_count}', f'Malformed row: {row}')
                    found = False
                    break
                else:
                    found = True
                    verse_data[field] = row[idx]
            if not found:
                continue
            if 'Reference' not in verse_data or ':' not in verse_data['Reference']:
               continue
            chapter = verse_data['Reference'].split(':')[0].lstrip('0')
            verse = re.split('[,-]', verse_data['Reference'].split(':')[1])[0].lstrip('0')
            tn_rc_link = f'rc://{self.language_id}/{self.name}/help/{self.project_id}/{self.pad(chapter)}/{verse.zfill(3)}/{verse_data["ID"]}'
            tn_title = verse_data["GLQuote"] if verse_data["GLQuote"] else verse_data["Quote"]
            tn_rc = self.create_rc(tn_rc_link, title=tn_title)
            verse_data['title'] = tn_title
            verse_data['rc'] = tn_rc
            if chapter not in book_data:
                book_data[chapter] = OrderedDict()
            if verse not in book_data[chapter]:
                book_data[chapter][verse] = []
            book_data[str(chapter)][str(verse)].append(verse_data)
        self.tn_book_data = book_data

    def get_tn_html(self):
        tn_html = f'''
<section>
<article id="{self.language_id}-{self.name}-{self.project_id}-cover" class="resource-title-page no-header">
    <img src="{self.main_resource.logo_url}" class="logo" alt="UTN">
    <h1 class="section-header">{self.title}</h1>
    <h2 class="section-header no-header">{self.project_title}</h2>
</article>
'''
        if 'front' in self.tn_book_data and 'intro' in self.tn_book_data['front']:
            book_intro = markdown.markdown(self.tn_book_data['front']['intro'][0]['Note'].replace('<br>', '\n').replace('\\n', "\n"), extensions=['md_in_html', 'tables', 'footnotes'])
            book_intro_title = html_tools.get_title_from_html(book_intro)
            book_intro = self.fix_tn_links(book_intro, 'intro')
            book_intro = html_tools.make_first_header_section_header(book_intro, level=3)
            # HANDLE FRONT INTRO RC LINKS
            book_intro_rc_link = f'rc://{self.language_id}/{self.name}/help/{self.project_id}/front/intro'
            book_intro_rc = self.add_rc(book_intro_rc_link, title=book_intro_title)
            book_intro = f'''
    <article id="{book_intro_rc.article_id}">
        {book_intro}
    </article>
'''
            book_intro_rc.set_article(book_intro)
            tn_html += book_intro
        for chapter in BOOK_CHAPTER_VERSES[self.project_id]:
            self.log.info(f'Chapter {chapter}...')
            chapter_title = f'{self.project_title} {chapter}'
            # HANDLE INTRO RC LINK
            chapter_rc_link = f'rc://{self.language_id}/{self.name}/help/{self.project_id}/{self.pad(chapter)}'
            chapter_rc = self.add_rc(chapter_rc_link, title=chapter_title)
            tn_html += f'''
    <section id="{chapter_rc.article_id}" class="chapter">
        <h2 class="section-header" toc-level="3">{chapter_title}</h2>
'''
            if chapter in self.tn_book_data and 'intro' in self.tn_book_data[chapter]:
                self.log.info('Generating chapter info...')
                chapter_intro = markdown.markdown(self.tn_book_data[chapter]['intro'][0]['Note'].replace('<br>', "\n").replace('\\n', "\n"), extensions=['md_in_html', 'tables', 'footnotes'])
                # Remove leading 0 from chapter header
                chapter_intro = re.sub(r'<h(\d)>([^>]+) 0+([1-9])', r'<h\1>\2 \3', chapter_intro, 1, flags=re.MULTILINE | re.IGNORECASE)
                chapter_intro = html_tools.make_first_header_section_header(chapter_intro, level=4, no_toc=True)
                chapter_intro_title = html_tools.get_title_from_html(chapter_intro)
                chapter_intro = self.fix_tn_links(chapter_intro, chapter)
                # HANDLE INTRO RC LINK
                chapter_intro_rc_link = f'rc://{self.language_id}/{self.name}/help/{self.project_id}/{self.pad(chapter)}/chapter_intro'
                chapter_intro_rc = self.add_rc(chapter_intro_rc_link, title=chapter_intro_title)
                chapter_intro = f'''
        <article id="{chapter_intro_rc.article_id}">
            {chapter_intro}
        </article>
'''
                chapter_intro_rc.set_article(chapter_intro)
                tn_html += chapter_intro

            for verse in range(1,  int(BOOK_CHAPTER_VERSES[self.project_id][chapter]) + 1):
                verse = str(verse)
                self.log.info(f'Generating verse {chapter}:{verse}...')
                tn_html += self.get_tn_article(chapter, verse)
            tn_html += '''
    </section>
'''
        tn_html += '''
</section>
'''
        self.log.info('Done generating TN HTML.')
        return tn_html

    def get_tn_article(self, chapter, verse):
        tn_title = f'{self.project_title} {chapter}:{verse}'
        tn_rc_link = f'rc://{self.language_id}/{self.name}/help/{self.project_id}/{self.pad(chapter)}/{verse.zfill(3)}'
        tn_rc = self.add_rc(tn_rc_link, title=tn_title)
        tn_article = f'''
                <article id="{tn_rc.article_id}">
                    <h2 class="section-header no-toc">{tn_title}</h2>
                    <div class="notes">
                        {self.get_tn_article_text(chapter, verse)}
                    </div>
                </article>
'''
        tn_rc.set_article(tn_article)
        return tn_article

    def get_tn_article_text(self, chapter, verse):
        verse_notes = ''
        if chapter in self.tn_book_data and verse in self.tn_book_data[chapter]:
            for tn_note in self.tn_book_data[chapter][verse]:
                note = markdown.markdown(tn_note['Note'].replace('<br>', "\n").replace('\\n', "\n"), extensions=['md_in_html', 'tables', 'footnotes'])
                note = re.sub(r'</*p[^>]*>', '', note, flags=re.IGNORECASE | re.MULTILINE)
                support = f" (See: [[{tn_note['SupportReference']}]])" if tn_note["SupportReference"] else ""
                verse_notes += f'''
        <div id="{tn_note['rc'].article_id}" class="verse-note">
            <h3 class="verse-note-title">{tn_note['title']}</h3>
            <div class="verse-note-text">
                {note}{support}
            </div>
        </div>
'''
        else:
            verse_notes += f'''
        <div class="no-notes">
            ({self.translate('no_notes_for_this_verse')})
        </div>
'''
        verse_notes = self.fix_tn_links(verse_notes, chapter)
        return verse_notes

    def fix_tn_links(self, html, chapter):
        def replace_link(match):
            before_href = match.group(1)
            link = match.group(2)
            after_href = match.group(3)
            linked_text = match.group(4)
            new_link = link
            if link.startswith('../../'):
                # link to another book, which we don't link to so link removed
                return linked_text
            elif link.startswith('../'):
                # links to another verse in another chapter
                link = os.path.splitext(link)[0]
                parts = link.split('/')
                if len(parts) == 3:
                    # should have two numbers, the chapter and the verse
                    c = parts[1]
                    v = parts[2]
                    new_link = f'rc://{self.language_id}/{self.name}/help/{self.project_id}/{self.pad(c)}/{v.zfill(3)}'
                if len(parts) == 2:
                    # shouldn't be here, but just in case, assume link to the first verse of the given chapter
                    c = parts[1]
                    new_link = f'rc://{self.language_id}/{self.name}/help/{self.project_id}/{self.pad(c)}/001'
            elif link.startswith('./'):
                # link to another verse in the same chapter
                link = os.path.splitext(link)[0]
                parts = link.split('/')
                v = parts[1]
                new_link = f'rc://{self.language_id}/{self.name}/help/{self.project_id}/{self.pad(chapter)}/{v.zfill(3)}'
            return f'<a{before_href}href="{new_link}"{after_href}>{linked_text}</a>'
        regex = re.compile(r'<a([^>]+)href="(\.[^"]+)"([^>]*)>(.*?)</a>')
        html = regex.sub(replace_link, html)
        return html
