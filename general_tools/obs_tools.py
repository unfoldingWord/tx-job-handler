import os
import markdown
from bs4 import BeautifulSoup


def get_obs_chapter_data(repo_dir, chapter_num):
    obs_chapter_data = {
        'title': None,
        'frames': [],
        'bible_reference': None
    }
    obs_chapter_file = os.path.join(repo_dir, 'content', f'{chapter_num}.md')
    if not os.path.isfile(obs_chapter_file):
        obs_chapter_file = os.path.join(repo_dir, f'{chapter_num}.md')
    if os.path.isfile(obs_chapter_file):
        print(obs_chapter_file)
        with open(obs_chapter_file, "r", encoding="utf-8") as input_file:
            markdown_text = input_file.read()
        obs_chapter_html = markdown.markdown(markdown_text, extensions=['md_in_html', 'tables', 'footnotes'])
        soup = BeautifulSoup(obs_chapter_html, 'html.parser')
        obs_chapter_data['title'] = soup.h1.text
        paragraphs = soup.find_all('p')
        frame = {
            'image': '',
            'text': ''
        }
        for idx, p in enumerate(paragraphs):
            if p.img:
                src = p.img['src'].split('?')[0]
                if frame['image']:
                    obs_chapter_data['frames'].append(frame)
                    frame = {
                        'image': '',
                        'text': ''
                    }
                frame['image'] = src
                p.img.extract()
            if p.text:
                if idx == len(paragraphs) - 1 and frame['text']:
                    obs_chapter_data['bible_reference'] = p.text
                else:
                    frame['text'] += str(p)
        if frame['image']:
            obs_chapter_data['frames'].append(frame)
    return obs_chapter_data
