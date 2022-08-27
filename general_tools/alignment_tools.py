#!/usr/bin/env python3
#
#  Copyright (c) 2020 unfoldingWord
#  http://creativecommons.org/licenses/MIT/
#  See LICENSE file for details.
#
#  Contributors:
#  Richard Mahn <rich.mahn@unfoldingword.org>

import re
import string
from general_tools.file_utils import load_json_object

hebrew_punctuation = '׃׀־׳״׆'
punctuation = string.punctuation + hebrew_punctuation


def get_quote_combinations(quote):
    quote_combinations = []
    for i in range(0, len(quote)):
        indexes = [i]
        text = [quote[i]['word']]
        quote_combinations.append({
            'word': text[:],
            'occurrence': quote[i]['occurrence'],
            'indexes': indexes[:],
            'found': False
        })
        for j in range(i + 1, len(quote)):
            indexes.append(j)
            text.append(quote[j]["word"])
            quote_combinations.append({
                'word': text[:],
                'occurrence': 1,
                'indexes': indexes[:],
                'found': False
            })
    return quote_combinations


def split_string_into_quote(text, occurrence=1):
    if occurrence < 1:
        occurrence = 1
    quote = []
    parts = re.split('…', text)
    for part_idx, part in enumerate(parts):
        words = list(filter(None, re.split(rf'([{punctuation}]+)|\s+', part)))
        quote.append([])
        for word_idx, word in enumerate(words):
            if word.strip():
                quote[part_idx].append({
                    'word': word.strip(),
                    'occurrence': occurrence
                })
    return quote


def split_string_into_alignment(text, occurrence=1):
    alignments = []
    parts = re.split('…', text)
    for part_idx, part in enumerate(parts):
        words = list(filter(None, re.split(rf'([{punctuation}]+|\s+)', part)))
        alignments.append([])
        for word_idx, word in enumerate(words):
            alignments[part_idx].append({
                'word': word,
                'occurrence': occurrence
            })
    return alignments


def convert_single_dimensional_quote_to_multidimensional(quote):
    multi_quote = []
    words = []
    for word in quote:
        if 'word' in word:
            if word['word'] == '…':
                multi_quote.append(words)
                words = []
            else:
                words.append({
                    'word': word['word'],
                    'occurrence': word['occurrence']
                })
    multi_quote.append(words)
    return multi_quote


def get_alignment(verse_objects, quote, occurrence=1):
    orig_quote = quote
    if isinstance(quote, str):
        quote = split_string_into_quote(quote, occurrence)
    elif not isinstance(quote[0], list):
        quote = convert_single_dimensional_quote_to_multidimensional(quote)

    alignment = []
    for group in quote:
        quote_combinations = get_quote_combinations(group)
        alignment += get_alignment_by_combinations(verse_objects, group, quote_combinations)

    for phrase in quote:
        for word in phrase:
            if 'found' not in word and re.sub(rf'[{punctuation}]', '', word['word']):
                return None
    return alignment


def get_alignment_by_combinations(verse_objects, quote, quote_combinations, found=False):
    alignments = []
    in_between_alignments = []
    last_found = False
    for verse_object in verse_objects:
        my_found = found
        if 'type' in verse_object and verse_object['type'] == 'milestone':
            if 'content' in verse_object:
                for combo in quote_combinations:
                    joined = ''.join(combo['word'])
                    joined_with_spaces = ' '.join(combo['word'])
                    joined_with_joiner = '\u2060'.join(combo['word'])
                    if combo['occurrence'] == verse_object['occurrence'] and \
                            (joined == verse_object['content'] or
                             joined_with_spaces == verse_object['content'] or
                             joined_with_joiner == verse_object['content']):
                        my_found = True
                        for index in combo['indexes']:
                            quote[index]['found'] = True
                        break
                if not my_found:
                    last_found = False
                    in_between_alignments = []
            if 'children' in verse_object:
                my_alignments = get_alignment_by_combinations(verse_object['children'], quote, quote_combinations,
                                                              my_found)
                if not found and my_found:
                    if last_found:
                        alignments[-1] += in_between_alignments + my_alignments
                        in_between_alignments = []
                    else:
                        alignments.append(my_alignments)
                        last_found = True
                else:
                    alignments += my_alignments
        elif 'text' in verse_object and (found or last_found):
            alignment = {
                'word': verse_object['text'],
                'occurrence': verse_object['occurrence'] if 'occurrence' in verse_object else 0
            }
            if found:
                alignments.append(alignment)
            elif last_found:
                in_between_alignments.append(alignment)
    return alignments


def flatten_alignment(alignment):
    if not alignment:
        return alignment
    if isinstance(alignment, str):
        return alignment
    part_strs = []
    for part in alignment:
        words = ''
        for word in part:
            words += word['word']
        part_strs.append(words)
    return '…'.join(part_strs)


def flatten_quote(quote):
    if not quote or isinstance(quote, str):
        return quote
    words = []
    for word in quote:
        words.append(word['word'])
    return ' '.join(words)


def tests():
    # TIT	1	8	xy12	figs-doublet	δίκαιον, ὅσιον	1	righteous, holy
    group_data = load_json_object('/Users/richmahn/working/resources/en/translationHelps/translationNotes/v23/figures/groups/tit/figs-doublet.json')
    chapter_verse_objects = load_json_object('/Users/richmahn/working/resources/en/bibles/ult/v8/tit/1.json')
    quote = group_data[1]["contextId"]["quote"]
    verse_objects = chapter_verse_objects["8"]["verseObjects"]
    alignments = get_alignment(verse_objects, quote)
    print(alignments)
    return

    # TIT	1	2	r2gj		πρὸ χρόνων αἰωνίων	1	before all the ages of time
    chapter_verse_objects = load_json_object('/Users/richmahn/working/resources/en/bibles/ult/v8/tit/1.json')
    quote = 'πρὸ χρόνων αἰωνίων'
    occurrence = 1
    verse_objects = chapter_verse_objects["2"]["verseObjects"]
    alignments = get_alignment(verse_objects, quote, occurrence)
    print(alignments)
    return

    string = 'בִּ⁠ימֵי֙ שְׁפֹ֣ט הַ⁠שֹּׁפְטִ֔ים'
    group_data = load_json_object(
        '/Users/richmahn/working/resources/en/translationHelps/translationNotes/v23/other/groups/rut/grammar-connect-time-simultaneous.json')
    chapter_verse_objects = load_json_object('/Users/richmahn/working/resources/en/bibles/ult/v8/rut/1.json')

    quote = group_data[0]["contextId"]["quote"]
    verse_objects = chapter_verse_objects["1"]["verseObjects"]
    alignments = get_alignment(verse_objects, quote)
    print(alignments)

    # RUT	4	22	abcd	figs-explicit	אֶת־דָּוִֽד	1	David
    group_data = load_json_object(
        '/Users/richmahn/working/resources/en/translationHelps/translationNotes/v23/culture/groups/rut/figs-explicit.json')
    chapter_verse_objects = load_json_object('/Users/richmahn/working/resources/en/bibles/ult/v8/rut/4.json')

    quote = group_data[12]["contextId"]["quote"]
    occurrence = group_data[12]["contextId"]["occurrence"]
    verse_objects = chapter_verse_objects["22"]["verseObjects"]
    alignments = get_alignment(verse_objects, quote, occurrence)
    print(alignments)

    # RUT	4	17	f9ha	figs-explicit	אֲבִ֥י דָוִֽד	1	the father of David
    quote = group_data[11]["contextId"]["quote"]
    occurrence = group_data[11]["contextId"]["occurrence"]
    verse_objects = chapter_verse_objects["17"]["verseObjects"]
    alignments = get_alignment(verse_objects, quote, occurrence)
    print(alignments)

    # RUT	4	19	rl3k	translate-names	וְ⁠חֶצְרוֹן֙…עַמִּֽינָדָֽב׃	1	Hezron…Amminadab
    group_data = load_json_object(
        '/Users/richmahn/working/resources/en/translationHelps/translationNotes/v23/culture/groups/rut/translate-names.json')
    quote = group_data[-1]["contextId"]["quote"]
    occurrence = group_data[-1]["contextId"]["occurrence"]
    verse_objects = chapter_verse_objects["17"]["verseObjects"]
    alignments = get_alignment(verse_objects, quote, occurrence)
    print(alignments)

    # RUT	1	4	aee6		שֵׁ֤ם הָֽ⁠אַחַת֙…וְ⁠שֵׁ֥ם הַ⁠שֵּׁנִ֖י	1	the name of the first woman was…and the name of the second woman was
    quote = 'שֵׁ֤ם הָֽ⁠אַחַת֙…וְ⁠שֵׁ֥ם הַ⁠שֵּׁנִ֖י'
    occurrence = 1
    chapter_verse_objects = load_json_object('/Users/richmahn/working/resources/en/bibles/ult/v8/rut/1.json')
    verse_objects = chapter_verse_objects["4"]["verseObjects"]
    alignments = get_alignment(verse_objects, quote, occurrence)
    print(alignments)


if __name__ == '__main__':
    tests()