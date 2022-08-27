#!/usr/bin/env python3
#
#  Copyright (c) 2020 unfoldingWord
#  http://creativecommons.org/licenses/MIT/
#  See LICENSE file for details.
#
#  Contributors:
#  Richard Mahn <rich.mahn@unfoldingword.org>

"""
This script generates the HTML and PDF SQ documents
"""
import os
import re
import markdown2
import general_tools.html_tools as html_tools
from door43_tools.subjects import TSV_TRANSLATION_QUESTIONS, ALIGNED_BIBLE
from bs4 import BeautifulSoup
from collections import OrderedDict
from .pdf_converter import represent_int
from .tsv_pdf_converter import TsvPdfConverter
from tx_usfm_tools.singleFilelessHtmlRenderer import SingleFilelessHtmlRenderer
from door43_tools.bible_books import BOOK_CHAPTER_VERSES
from general_tools.alignment_tools import flatten_alignment
from general_tools.file_utils import read_file, get_latest_version_path
from general_tools.usfm_utils import unalign_usfm

DEFAULT_ULT_ID = 'ult'
DEFAULT_UST_ID = 'ust'
QUOTES_TO_IGNORE = ['general information:', 'connecting statement:']
PROJECT_FULL = 'full' # Single PDF for all books of the Bible 

class TqPdfConverter(TsvPdfConverter):
    my_subject = TSV_TRANSLATION_QUESTIONS

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.tq_book_data = OrderedDict()

    def get_default_project_ids(self):
       return [PROJECT_FULL] + list(map(lambda project: project['identifier'], self.main_resource.projects))

    @property
    def project_title(self):
        if self.project_id == PROJECT_FULL:
            return ''
        else:
            if self.project:
                return self.project['title']

    @property
    def file_id_project_str(self):
        if self.project_id and self.project_id != PROJECT_FULL:
            return super().file_id_project_str.upper()
        else:
            return ''

    def get_appendix_rcs(self):
        return

    def get_body_html(self):
        self.log.info('Creating TQ for {0}...'.format(self.file_project_and_ref))
        self.process_bibles()
        html = self.get_tq_html()
        del self.tq_book_data
        del self.book_data
        return html

    def populate_tq_book_data(self):
        book_filename = f'{self.main_resource.identifier}_{self.project_id.upper()}.tsv'
        book_filepath = os.path.join(self.main_resource.repo_dir, book_filename)
        if not os.path.isfile(book_filepath):
            return
        book_data = {}
        reader = self.unicode_csv_reader(open(book_filepath))
        header = next(reader)
        row_count = 1
        for row in reader:
            row_count += 1
            found = False
            verse_data = {}
            for idx, field in enumerate(header):
                field = field.strip()
                if idx >= len(row):
                    self.log.error(f'ERROR: {book_filepath} is malformed at row {row_count}: {row}')
                    self.add_error_message(self.create_rc(f'{book_filename}#{row_count}'), f'Line {row_count}', f'Malformed row: {row}')
                    found = False
                    break
                else:
                    found = True
                    verse_data[field] = row[idx]
            if not found:
                continue
            
            reference = verse_data['Reference']
            if ':' not in reference:
                continue
            chapter, verse_str = reference.split(':')
            chapter = chapter.lstrip('0')
            verse_str = verse_str.strip().lstrip('0')
            multiverse = False
            if ',' in verse_str:
                start_verse = verse_str.split(',')[0].strip()
                multiverse = True
            else:
                start_verse = verse_str
            if '-' in start_verse:
                start_verse = start_verse.split('-')[0].strip()
                multiverse = True
            if verse_data['Question'] and verse_data['Response'] and chapter.isdigit() and start_verse.isdigit():
                rc_link = f'rc://{self.language_id}/{self.main_resource.identifier}/help/{self.project_id}/{self.pad(chapter)}/{start_verse.zfill(3)}/{verse_data["ID"]}'
                question = f'{verse_data["Question"]}'
                rc_link = f'rc://{self.language_id}/{self.main_resource.identifier}/help///{self.project_id}/{self.pad(chapter)}/{start_verse.zfill(3)}'
                data = {
                    'start_verse': start_verse,
                    'reference': verse_str if multiverse else '',
                    'rc': self.create_rc(rc_link, title=question),
                    'question': question,
                    'response': verse_data['Response'],
                }
                if chapter not in book_data:
                    book_data[chapter] = OrderedDict()
                if start_verse not in book_data[chapter]:
                    book_data[chapter][start_verse] = []
                book_data[chapter][start_verse].append(data)
        self.tq_book_data = book_data

    def get_tq_html(self):
        full = False
        if not self.project_id:
            self.project_id = PROJECT_FULL
        if self.project_id == PROJECT_FULL:
            projects = self.main_resource.projects
            full = True
        else:
            projects = [self.main_resource.find_project(self.project_id)]
        tq_html = ""

        for idx, project in enumerate(projects):
            self.project_id = project['identifier']
            self.tq_book_data = OrderedDict()
            self.book_data = OrderedDict()
            for resource in self.resources.values():
                if resource.subject == ALIGNED_BIBLE:
                    self.populate_book_data(resource.identifier, resource.language_id)
            self.populate_book_data(self.ol_bible_id, self.ol_lang_code)
            self.populate_tq_book_data()

            tq_html += f'''
<section id="{self.language_id}-{self.name}-{project["identifier"]}" class="{self.name}">
    <h1 class="section-header hidden{" no-toc" if idx > 0 else ""}">{self.simple_title}</h1>
        <h2 class="section-header">{project["title"]}</h2>
'''
            for chapter in BOOK_CHAPTER_VERSES[project["identifier"]]:
                self.log.info(f'Chapter {chapter}...')
                chapter_title = f'{project["title"]} {chapter}'
                # HANDLE INTRO RC LINK
                chapter_rc_link = f'rc://{self.language_id}/{self.main_resource.identifier}/help/{project["identifier"]}/{self.pad(chapter)}'
                chapter_rc = self.add_rc(chapter_rc_link, title=chapter_title)
                tq_html += f'''
        <section id="{chapter_rc.article_id}" class="chapter no-break-articles">
            <h3 class="section-header{" no-toc" if len(projects) > 0 else ""}" header-level="2">{chapter_title}</h3>
'''
                for verse in range(1,  int(BOOK_CHAPTER_VERSES[project["identifier"]][chapter]) + 1):
                    verse = str(verse)
                    self.log.info(f'Generating verse {chapter}:{verse}...')
                    tq_html += self.get_tq_article(chapter, verse)
                tq_html += '''
        </section>
    '''
            tq_html += '''
    </section>
    '''
        if full:
            self.project_id = PROJECT_FULL
        self.log.info('Done generating TQ HTML.')
        return tq_html

    def get_tq_article(self, chapter, verse):
        tq_title = f'{self.project_title} {chapter}:{verse}'
        tq_rc_link = f'rc://{self.language_id}/{self.main_resource.identifier}/help/{self.project_id}/{self.pad(chapter)}/{verse.zfill(3)}'
        tq_rc = self.add_rc(tq_rc_link, title=tq_title)
        ult_text = self.get_plain_scripture(self.ult.identifier, chapter, verse)
        ust_text = self.get_plain_scripture(self.ust.identifier, chapter, verse)

        tq_article = f'''
                <article id="{tq_rc.article_id}">
                    <h4 class="section-header no-toc" header-level="2">{tq_title}</h4>
                    <div class="notes">
                            <div class="scripture">
                                <h3 class="bible-resource-title">{self.ult.identifier.upper()}</h3>
                                <div class="bible-text">{ult_text}</div>
'''
        if ust_text:
            tq_article += f'''
                                <h3 class="bible-resource-title">{self.ust.identifier.upper()}</h3>
                                <div class="bible-text">{ust_text}</div>
'''
        tq_article += f'''
                            </div>
                            <div class="questions">
                                {self.get_tq_article_text(chapter, verse)}
                            </div>
                    </div>
                </article>
'''
        tq_rc.set_article(tq_article)
        return tq_article

    def get_tq_article_text(self, chapter, verse):
        verse_questions = ''
        if chapter in self.tq_book_data and verse in self.tq_book_data[chapter]:
            for data in self.tq_book_data[chapter][verse]:
                verse_questions += f'''
        <div id="{data['rc'].article_id}" class="verse-question">
            <h5 class="verse-question-title">{data['question']}{f" (vv{data['reference']})" if data['reference'] else ''}</h5>
            <div class="verse-question-text">
                {data['response']}
            </div>
        </div>
'''
        else:
            verse_questions += f'''
        <div class="no-questions">
            ({self.translate('no_questions_for_this_verse')})
        </div>
'''
        verse_questions = self.fix_tq_links(verse_questions, chapter)
        return verse_questions

    def get_scripture_with_tq_quotes(self, bible_id, chapter, verse, rc, scripture):
        if not scripture:
            scripture = self.get_plain_scripture(bible_id, chapter, verse)
        footnotes_split = re.compile('<div class="footnotes">', flags=re.IGNORECASE | re.MULTILINE)
        verses_and_footnotes = re.split(footnotes_split, scripture, maxsplit=1)
        scripture = verses_and_footnotes[0]
        footnote = ''
        if len(verses_and_footnotes) == 2:
            footnote = f'<div class="footnotes">{verses_and_footnotes[1]}'
        if chapter in self.tq_book_data and verse in self.tq_book_data[chapter]:
            tq_notes = self.tq_book_data[chapter][verse]
        else:
            tq_notes = []
        orig_scripture = scripture
        for tq_note_idx, tq_note in enumerate(tq_notes):
            occurrence = 1
            if represent_int(tq_note['Occurrence']) and int(tq_note['Occurrence']) > 0:
                occurrence = int(tq_note['Occurrence'])
            gl_quote_phrase = [[{
                'word': tq_note['GLQuote'],
                'occurrence': occurrence
            }]]
            phrase = tq_note['alignments'][bible_id]
            if not phrase:
                phrase = gl_quote_phrase
            if flatten_alignment(phrase).lower() in QUOTES_TO_IGNORE:
                continue
            split = ''
            if len(phrase) > 1:
                split = ' split'
            tag = f'<span class="highlight phrase phrase-{tq_note_idx+1}{split}">'
            marked_verse_html = html_tools.mark_phrases_in_html(scripture, phrase, tag=tag)
            if not marked_verse_html:
                fix = None
                if flatten_alignment(phrase).lower() not in QUOTES_TO_IGNORE:
                    if tq_note['GLQuote']:
                        marked_with_gl_quote = html_tools.mark_phrases_in_html(scripture, gl_quote_phrase)
                        if marked_with_gl_quote:
                            fix = tq_note['GLQuote']
                    self.add_bad_highlight(rc, orig_scripture, tq_note['rc'], tq_note['GLQuote'], fix)
            else:
                scripture = marked_verse_html
        scripture += footnote
        return scripture

    def fix_tq_links(self, html, chapter):
        html = self.fix_tsv_links(html, chapter)
        return html
