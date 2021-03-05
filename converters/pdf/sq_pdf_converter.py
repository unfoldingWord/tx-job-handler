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
from door43_tools.subjects import TSV_STUDY_QUESTIONS
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


class SqPdfConverter(TsvPdfConverter):
    my_subject = TSV_STUDY_QUESTIONS

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.sq_book_data = OrderedDict()

    @property
    def name(self):
        return 'sq'

    @property
    def file_id_project_str(self):
        if self.project_id:
            return f'_{self.book_number.zfill(2)}-{self.project_id.upper()}'
        else:
            return ''

    def get_appendix_rcs(self):
        return

    def get_body_html(self):
        self.log.info('Creating SQ for {0}...'.format(self.file_project_and_ref))
        self.process_bibles()
        self.populate_book_data(self.ult_id)
        self.populate_book_data(self.ust_id)
        self.populate_book_data(self.ol_bible_id, self.ol_lang_code)
        self.populate_sq_book_data()
        html = self.get_sq_html()
        self.sq_book_data = None
        return html

    def get_usfm_from_verse_objects(self, verse_objects):
        usfm = ''
        for idx, obj in enumerate(verse_objects):
            if obj['type'] == 'milestone':
                usfm += self.get_usfm_from_verse_objects(obj['children'])
            elif obj['type'] == 'word':
                if not self.next_follows_quote and obj['text'] != 's':
                    usfm += ' '
                usfm += obj['text']
                self.next_follows_quote = False
            elif obj['type'] == 'text':
                obj['text'] = obj['text'].replace('\n', '').strip()
                if not self.open_quote and len(obj['text']) > 2 and obj['text'][-1] == '"':
                    obj['text'] = f"{obj['text'][:-1]} {obj['text'][-1]}"
                if not self.open_quote and obj['text'] == '."':
                    obj['text'] = '. "'
                if len(obj['text']) and obj['text'][0] == '"' and not self.open_quote and obj['text'] not in ['-', '—']:
                    usfm += ' '
                usfm += obj['text']
                if obj['text'].count('"') == 1:
                    self.open_quote = not self.open_quote
                if self.open_quote and '"' in obj['text'] or obj['text'] in ['-', '—', '(', '[']:
                    self.next_follows_quote = True
            elif obj['type'] == 'quote':
                obj['text'] = obj['text'].replace('\n', '').strip() if 'text' in obj else ''
                if idx == len(verse_objects) - 1 and obj['tag'] == 'q' and len(obj['text']) == 0:
                    self.last_ended_with_quote_tag = True
                else:
                    usfm += f"\n\\{obj['tag']} {obj['text'] if len(obj['text']) > 0 else ''}"
                if obj['text'].count('"') == 1:
                    self.open_quote = not self.open_quote
                if self.open_quote and '"' in obj['text']:
                    self.next_follows_quote = True
            elif obj['type'] == 'section':
                obj['text'] = obj['text'].replace('\n', '').strip() if 'text' in obj else ''
            elif obj['type'] == 'paragraph':
                obj['text'] = obj['text'].replace('\n', '').strip() if 'text' in obj else ''
                if idx == len(verse_objects) - 1 and not obj['text']:
                    self.last_ended_with_paragraph_tag = True
                else:
                    usfm += f"\n\\{obj['tag']}{obj['text']}\n"
            elif obj['type'] == 'footnote':
                obj['text'] = obj['text'].replace('\n', '').strip() if 'text' in obj else ''
                usfm += f' \\{obj["tag"]} {obj["content"]} \\{obj["tag"]}*'
            else:
                self.log.error("ERROR! Not sure what to do with this:")
                self.log.error(obj)
                exit(1)
        return usfm

    def populate_book_data(self, bible_id, lang_code=None):
        if not lang_code:
            lang_code = self.lang_code
        bible_path = os.path.join(self.resources_dir, lang_code, 'bibles', bible_id)
        if not bible_path:
            self.log.error(f'{bible_path} not found!')
            exit(1)
        bible_version_path = get_latest_version_path(bible_path)
        if not bible_version_path:
            self.log.error(f'No versions found in {bible_path}!')
            exit(1)

        book_data = OrderedDict()
        book_file = os.path.join(self.resources[bible_id].repo_dir, f'{self.book_number}-{self.project_id.upper()}.usfm')
        book_usfm = read_file(book_file)

        unaligned_usfm = unalign_usfm(book_usfm)
        self.log.info(f'Converting {self.project_id.upper()} from USFM to HTML...')
        book_html, warnings = SingleFilelessHtmlRenderer({self.project_id.upper(): unaligned_usfm}).render()
        html_verse_splits = re.split(r'(<span id="[^"]+-ch-0*(\d+)-v-(\d+(?:-\d+)?)" class="v-num">)', book_html)
        usfm_chapter_splits = re.split(r'\\c ', unaligned_usfm)
        usfm_verse_splits = None
        chapter_verse_index = 0
        for i in range(1, len(html_verse_splits), 4):
            chapter = html_verse_splits[i+1]
            verses = html_verse_splits[i+2]
            if chapter not in book_data:
                book_data[chapter] = OrderedDict()
                usfm_chapter = f'\\c {usfm_chapter_splits[int(chapter)]}'
                usfm_verse_splits = re.split(r'\\v ', usfm_chapter)
                chapter_verse_index = 0
            chapter_verse_index += 1
            verse_usfm = f'\\v {usfm_verse_splits[chapter_verse_index]}'
            verse_html = html_verse_splits[i] + html_verse_splits[i+3]
            verse_html = re.split('<h2', verse_html)[0]  # remove next chapter since only split on verses
            verse_soup = BeautifulSoup(verse_html, 'html.parser')
            for tag in verse_soup.find_all():
                if (not tag.contents or len(tag.get_text(strip=True)) <= 0) and tag.name not in ['br', 'img']:
                    tag.decompose()
            verse_html = str(verse_soup)
            verses = re.findall(r'\d+', verses)
            for verse in verses:
                verse = verse.lstrip('0')
                book_data[chapter][verse] = {
                    'usfm': verse_usfm,
                    'html': verse_html
                }
        self.book_data[bible_id] = book_data

    def populate_sq_book_data(self):
        book_filename = f'{self.lang_code}_{self.main_resource.identifier}_{self.book_number}-{self.project_id.upper()}.tsv'
        book_filepath = os.path.join(self.main_resource.repo_dir, book_filename)
        if not os.path.isfile(book_filepath):
            return
        book_data = OrderedDict()
        reader = self.unicode_csv_reader(open(book_filepath))
        header = next(reader)
        row_count = 1
        for row in reader:
            row_count += 1
            verse_data = {
                'contextId': None,
                'row': row_count,
                'alignments': {
                    self.ult_id: None,
                    self.ust_id: None
                }
            }
            found = False
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
            chapter = verse_data['Chapter'].lstrip('0')
            verse = verse_data['Verse'].lstrip('0')
            if verse_data['Occurrence']:
                occurrence = int(verse_data['Occurrence'])
            else:
                occurrence = 1
            sq_rc_link = f'rc://{self.lang_code}/{self.main_resource.identifier}/help/{self.project_id}/{self.pad(chapter)}/{verse.zfill(3)}/{verse_data["ID"]}'
            sq_title = f'{verse_data["GLQuote"]}'
            if verse_data['OrigQuote']:
                context_id = None
                if not context_id and chapter.isdigit() and verse.isdigit():
                    context_id = {
                        'reference': {
                            'chapter': int(chapter),
                            'verse': int(verse)
                        },
                        'rc': f'rc://{self.lang_code}/{self.main_resource.identifier}/help///{self.project_id}/{self.pad(chapter)}/{verse.zfill(3)}',
                        'quote': verse_data['OrigQuote'],
                        'occurrence': occurrence,
                        'quoteString': verse_data['OrigQuote']
                    }
                if context_id:
                    context_id['rc'] += f'/{verse_data["ID"]}'
                    context_id['quoteString'] = verse_data['OrigQuote']
                    verse_data['contextId'] = context_id
                    verse_data['alignments'] = {
                        self.ult_id: self.get_aligned_text(self.ult_id, context_id),
                        self.ust_id: self.get_aligned_text(self.ust_id, context_id)
                    }
                if verse_data['alignments'][self.ult_id]:
                    sq_title = flatten_alignment(verse_data['alignments'][self.ult_id]) + f' ({self.ult_id.upper()})'
                    if verse_data['alignments'][self.ust_id]:
                        sq_title += '<br/>' + flatten_alignment(verse_data['alignments'][self.ust_id]) + f' ({self.ust_id.upper()})'
                else:
                    sq_title = f'{verse_data["GLQuote"]}'
            sq_rc = self.create_rc(sq_rc_link, title=sq_title)
            verse_data['title'] = sq_title
            verse_data['rc'] = sq_rc
            if chapter not in book_data:
                book_data[chapter] = OrderedDict()
            if verse not in book_data[chapter]:
                book_data[chapter][verse] = []
            book_data[str(chapter)][str(verse)].append(verse_data)
        self.sq_book_data = book_data

    def get_sq_html(self):
        sq_html = f'''
<section id="{self.lang_code}-{self.name}-{self.project_id}" class="{self.name}">
    <h1 class="section-header hidden">{self.simple_title}</h1>
        <h2 class="section-header">{self.project_title}</h2>
'''
        if 'front' in self.sq_book_data and 'intro' in self.sq_book_data['front']:
            book_intro = markdown2.markdown(self.sq_book_data['front']['intro'][0]['OccurrenceNote'].replace('<br>', '\n'))
            book_intro_title = html_tools.get_title_from_html(book_intro)
            book_intro = self.fix_sq_links(book_intro, 'intro')
            book_intro = html_tools.make_first_header_section_header(book_intro, level=3)
            # HANDLE FRONT INTRO RC LINKS
            book_intro_rc_link = f'rc://{self.lang_code}/{self.main_resource.identifier}/help/{self.project_id}/front/intro'
            book_intro_rc = self.add_rc(book_intro_rc_link, title=book_intro_title)
            book_intro = f'''
    <article id="{book_intro_rc.article_id}">
        {book_intro}
    </article>
'''
            book_intro_rc.set_article(book_intro)
            sq_html += book_intro
        for chapter in BOOK_CHAPTER_VERSES[self.project_id]:
            self.log.info(f'Chapter {chapter}...')
            chapter_title = f'{self.project_title} {chapter}'
            # HANDLE INTRO RC LINK
            chapter_rc_link = f'rc://{self.lang_code}/{self.main_resource.identifier}/help/{self.project_id}/{self.pad(chapter)}'
            chapter_rc = self.add_rc(chapter_rc_link, title=chapter_title)
            sq_html += f'''
    <section id="{chapter_rc.article_id}" class="chapter no-break-articles">
        <h3 class="section-header" header-level="2">{chapter_title}</h3>
'''
            if 'intro' in self.sq_book_data[chapter]:
                self.log.info('Generating chapter info...')
                chapter_intro = markdown2.markdown(self.sq_book_data[chapter]['intro'][0]['OccurrenceNote'].replace('<br>', "\n"))
                # Remove leading 0 from chapter header
                chapter_intro = re.sub(r'<h(\d)>([^>]+) 0+([1-9])', r'<h\1>\2 \3', chapter_intro, 1, flags=re.MULTILINE | re.IGNORECASE)
                chapter_intro = html_tools.make_first_header_section_header(chapter_intro, level=4, no_toc=True, header_level=3)
                chapter_intro_title = html_tools.get_title_from_html(chapter_intro)
                chapter_intro = self.fix_sq_links(chapter_intro, chapter)
                # HANDLE INTRO RC LINK
                chapter_intro_rc_link = f'rc://{self.lang_code}/{self.main_resource.identifier}/help/{self.project_id}/{self.pad(chapter)}/chapter_intro'
                chapter_intro_rc = self.add_rc(chapter_intro_rc_link, title=chapter_intro_title)
                chapter_intro = f'''
        <article id="{chapter_intro_rc.article_id}">
            {chapter_intro}
        </article>
'''
                chapter_intro_rc.set_article(chapter_intro)
                sq_html += chapter_intro

            for verse in range(1,  int(BOOK_CHAPTER_VERSES[self.project_id][chapter]) + 1):
                verse = str(verse)
                self.log.info(f'Generating verse {chapter}:{verse}...')
                sq_html += self.get_sq_article(chapter, verse)
            sq_html += '''
    </section>
'''
        sq_html += '''
</section>
'''
        self.log.info('Done generating SQ HTML.')
        return sq_html

    def get_sq_article(self, chapter, verse):
        sq_title = f'{self.project_title} {chapter}:{verse}'
        sq_rc_link = f'rc://{self.lang_code}/{self.main_resource.identifier}/help/{self.project_id}/{self.pad(chapter)}/{verse.zfill(3)}'
        sq_rc = self.add_rc(sq_rc_link, title=sq_title)
        ult_text = self.get_plain_scripture(self.ult_id, chapter, verse)
        ult_text = self.get_scripture_with_sq_quotes(self.ult_id, chapter, verse, self.create_rc(f'rc://{self.lang_code}/ult/bible/{self.project_id}/{chapter}/{verse}', ult_text), ult_text)
        ust_text = self.get_plain_scripture(self.ust_id, chapter, verse)
        ust_text = self.get_scripture_with_sq_quotes(self.ust_id, chapter, verse, self.create_rc(f'rc://{self.lang_code}/ust/bible/{self.project_id}/{chapter}/{verse}', ult_text), ust_text)

        sq_article = f'''
                <article id="{sq_rc.article_id}">
                    <h4 class="section-header no-toc" header-level="2">{sq_title}</h4>
                    <div class="notes">
                            <div class="col1">
                                <h3 class="bible-resource-title">{self.ult_id.upper()}</h3>
                                <div class="bible-text">{ult_text}</div>
                                <h3 class="bible-resource-title">{self.ust_id.upper()}</h3>
                                <div class="bible-text">{ust_text}</div>
                            </div>
                            <div class="col2">
                                {self.get_sq_article_text(chapter, verse)}
                            </div>
                    </div>
                </article>
'''
        sq_rc.set_article(sq_article)
        return sq_article

    def get_sq_article_text(self, chapter, verse):
        verse_questions = ''
        if verse in self.sq_book_data[chapter]:
            for sq_question in self.sq_book_data[chapter][verse]:
                question = markdown2.markdown(sq_question['OccurrenceNote'].replace('<br>', "\n"))
                question = re.sub(r'</*p[^>]*>', '', question, flags=re.IGNORECASE | re.MULTILINE)
                verse_questions += f'''
        <div id="{sq_question['rc'].article_id}" class="verse-question">
            <h5 class="verse-question-title">{sq_question['title']}</h5>
            <div class="verse-question-text">
                {question}
            </div>
        </div>
'''
        else:
            verse_questions += f'''
        <div class="no-questions">
            ({self.translate('no_questions_for_this_verse')})
        </div>
'''
        verse_questions = self.fix_sq_links(verse_questions, chapter)
        return verse_questions

    def get_scripture_with_sq_quotes(self, bible_id, chapter, verse, rc, scripture):
        if not scripture:
            scripture = self.get_plain_scripture(bible_id, chapter, verse)
        footnotes_split = re.compile('<div class="footnotes">', flags=re.IGNORECASE | re.MULTILINE)
        verses_and_footnotes = re.split(footnotes_split, scripture, maxsplit=1)
        scripture = verses_and_footnotes[0]
        footnote = ''
        if len(verses_and_footnotes) == 2:
            footnote = f'<div class="footnotes">{verses_and_footnotes[1]}'
        if verse in self.sq_book_data[chapter]:
            sq_notes = self.sq_book_data[chapter][verse]
        else:
            sq_notes = []
        orig_scripture = scripture
        for sq_note_idx, sq_note in enumerate(sq_notes):
            occurrence = 1
            if represent_int(sq_note['Occurrence']) and int(sq_note['Occurrence']) > 0:
                occurrence = int(sq_note['Occurrence'])
            gl_quote_phrase = [[{
                'word': sq_note['GLQuote'],
                'occurrence': occurrence
            }]]
            phrase = sq_note['alignments'][bible_id]
            if not phrase:
                phrase = gl_quote_phrase
            if flatten_alignment(phrase).lower() in QUOTES_TO_IGNORE:
                continue
            split = ''
            if len(phrase) > 1:
                split = ' split'
            tag = f'<span class="highlight phrase phrase-{sq_note_idx+1}{split}">'
            marked_verse_html = html_tools.mark_phrases_in_html(scripture, phrase, tag=tag)
            if not marked_verse_html:
                fix = None
                if flatten_alignment(phrase).lower() not in QUOTES_TO_IGNORE:
                    if sq_note['GLQuote']:
                        marked_with_gl_quote = html_tools.mark_phrases_in_html(scripture, gl_quote_phrase)
                        if marked_with_gl_quote:
                            fix = sq_note['GLQuote']
                    self.add_bad_highlight(rc, orig_scripture, sq_note['rc'], sq_note['GLQuote'], fix)
            else:
                scripture = marked_verse_html
        scripture += footnote
        return scripture

    def fix_sq_links(self, html, chapter):
        html = self.fix_tsv_links(html, chapter)
        return html
