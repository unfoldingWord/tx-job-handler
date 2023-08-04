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
        soup = BeautifulSoup(markdown.markdownFromFile(obs_chapter_file), 'html.parser')
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
