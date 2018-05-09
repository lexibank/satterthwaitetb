# coding=utf-8
from __future__ import unicode_literals, print_function

from clldutils.path import Path
from clldutils.misc import slug
from pylexibank.dataset import Metadata
from pylexibank.dataset import Dataset as BaseDataset
from pylexibank.util import getEvoBibAsBibtex

from clldutils.text import split_text, strip_brackets
import re

import itertools

class Dataset(BaseDataset):
    dir = Path(__file__).parent

    def cmd_install(self, **kw):
        # read all the lines in the text file; I'm also including the
        # ERRATA here, which has a tuple value for all entries (the first gloss
        # on the page): the correction to be applied at the beginning (which
        # will be split along pipes) and the number of leading items in
        # the list to replace
        lines = self.raw.read('phillips-tibeto-burman-data.txt').split('\n')
        ERRATA = {
            'earth':
                ('earth1|earth2', 2),
            'enter （去）[':
                ('enter|evening|extinguish|eye|fall|Hanzi|徃 (去) [徃来]', 7),
            'far':
                ('far|fart, to|fast|fat [of person]|fat [of meat]|father|fear, to|Hanzi|径', 8),
            'hard':
                ('hard|hate1|hate2|he|head|hear|Hanzi|硬|恨|讨厌（人）|他|头|听见|Pinyin', 15),
            'insect':
                ('insect|inside|itchy|joint|jump|kick|kidney|Hanzi|虫子|里面|痒|关节|跳|踢|肾', 13),
            'medicine':
                ('medicine|mend (clothes)|metal|milk|monkey', 4),
            'shadow':
                ('shadow|shallow|sharp1|sharp2|she|sheep|Hanzi|影子|浅|(刀) 快|锋利|她|羊|Pinyin|ying zi30|qian3|(dao) kuai14|feng li14|ta1|yang2|Baihong|a31 ba31 la55 sɤ55|de55|-|da55|a31 jo31|a55 dzɨ31', 28),
            'saliva':
                ('saliva|squeeze|stand up|star|steal|Hanzi|口水|压榨|站|星星|䫖', 9),
            'swell':
                ('swell|swim|tail|tall (of stature)|taste|ten|that|Hanzi|肿', 8),
            'wash':
                ('wash|water|wax gourd|wax|weave|Hanzi|洗|水|冬瓜|蜡|编织 [织(布)]|Pinyin|xi3|shui3|dong gua11|la4|bian zhi11|Baihong', 19),
        }

        # dictionary for the number of elements to remove at the end of the lists,
        # using the first English word in each list/page as index; by default only
        # the last element, the page number, will be removed, but some pages have
        # garbage characters and/or footnotes that need to be treated with these
        # exceptions
        DROP_FINAL = {
            'hard' : 3,
            'insect' : 2,
            'man' : 2,
            'medicine' : 4,
            'palm' : 4,
            'shadow' : 3,
            'saliva' : 2,
            'wash' : 3,
            'wood' : 2,
        }

        # split all pages with a list comprehension that might seem complex,
        # but it just identifies entries with 'English' or '\x0cEnglish' (the
        # first entry at the top of the page) and groups them; in practice
        # it works similar to a string .split()
        pages = [list(g) for k, g in
            itertools.groupby(lines, lambda x: x in ['English', '\x0cEnglish'])
            if not k]

        # conversion with the split above works reasonably well, but there some
        # errors; luckly, we can catch most of them with a simple rule: as
        # the table lines are read as empty strings, whenever we have two non
        # empty entries we should join them (they are mostly line breaks that
        # actually refer to the same content)
        page_data = []
        for page in pages:
            cells = [page[0]]
            for entry in page[1:]:
                if cells[-1] and entry:
                    cells[-1] = '%s %s' % (cells[-1], entry)
                else:
                    cells.append(entry)

            # remove empty lists, so it's easy to correct PDF conversion
            # errors (which likely mirrors the order the author edited his
            # Word source...) and we can refer to a page by its first
            # English gloss; also strip
            cells = [cell for cell in cells if cell]

            # apply errata and strip all cells, correcting problematic
            # Unicode characters
            if cells[0] in ERRATA:
                idx = cells[0]
                cells = ERRATA[idx][0].split('|') + cells[ERRATA[idx][1]:]
            cells = [cell.strip() for cell in cells]
            cells = [cell.replace('）', ')') for cell in cells] # FULLWIDTH PARENTHESIS

            # drop the last element (the page number), or more final elements
            # (like for cases when there are footnotes)
            if cells[0] in DROP_FINAL:
                cells = cells[:-DROP_FINAL[cells[0]]]
            else:
                cells = cells[:-1]

            # extract the concepts and all language entries (rows)
            row_idx = {
                'concepts' : (None,       'Hanzi'),
                'Hanzi' :    ('Hanzi',    'Pinyin'),
                'Mandarin' : ('Pinyin',   'Baihong'),
                'Baihong' :  ('Baihong',  'Biyue'),
                'Biyue' :    ('Biyue',    'Hani'),
                'Hani' :     ('Hani',     'Jinghpo'),
                'Jinghpo' :  ('Jinghpo',  'Jinuo'),
                'Jinuo' :    ('Jinuo',    'Kucong'),
                'Kucong' :   ('Kucong',   'Lahu Na'),
                'Lahu Na' :  ('Lahu Na',  'Lahu Shi'),
                'Lahu Shi' : ('Lahu Shi', 'Lisu'),
                'Lisu' :     ('Lisu',     'Nasu'),
                'Nasu' :     ('Nasu',     'Naxi'),
                'Naxi' :     ('Naxi',     'Nisu'),
                'Nisu' :     ('Nisu',     'Nosu'),
                'Nosu' :     ('Nosu',     'Nusu'),
                'Nusu' :     ('Nusu',     'Samei'),
                'Samei' :    ('Samei',    'Zaiwa'),
                'Zaiwa' :    ('Zaiwa',    'Zaozou'),
                'Zaozou' :   ('Zaozou',    None),
            }

            rows = {}
            for row_name, indexes in row_idx.items():
                if not indexes[0]:
                    row = cells[:cells.index(indexes[1])]
                elif not indexes[1]:
                    row = cells[cells.index(indexes[0]):]
                else:
                    row = cells[cells.index(indexes[0]):cells.index(indexes[1])]

                # if it is not the concept row, exclude the first element of
                # each row (it is the language name, we already have it)
                if row_name is not 'concepts':
                    rows[row_name] = row[1:]
                else:
                    rows[row_name] = row

            page_data.append(rows)

        with self.cldf as ds:
            ds.add_sources(*self.raw.read_bib())
            # add languages
            for lang in self.languages:
                ds.add_language(
                    ID=slug(lang['NAME']),
                    Glottocode=lang['GLOTTOCODE'],
                    Name=lang['GLOTTOLOG_NAME'],
                )

            # add concepts
            for concept_id in self.conceptlist.concepts:
                concept = self.conceptlist.concepts[concept_id]
                ds.add_concept(
                    ID=slug(concept.english),
                    Concepticon_ID=concept.concepticon_id,
                    Name=concept.english,
                    Concepticon_Gloss=concept.concepticon_gloss,
                )

            graphemes = []
            for page in page_data:
                # for each concept...
                for idx, english in enumerate(page['concepts']):
                    # for each language/key (except 'concepts' and 'Hanzi')...
                    for lang in self.languages:
                        # extract the value (raw transcription) and apply
                        # some initial correction before splitting into the
                        # various forms; before removing parentheses, we
                        # manually correct and preserve the few cases in which
                        # the parentheses are actual sound information and
                        # not comments
                        value = page[lang['NAME']][idx]
                        value = value.replace('(y)', 'y')
                        value = value.replace('(r)', 'r')
                        value = value.replace('(ɨ)', 'ɨ')
                        value = strip_brackets(value, brackets={'(':')'})

                        for form in split_text(value, separators=';/'):
                            # correct forms with glosses without parentheses
                            form = form.replace('= song', '')
                            form = form.replace('= sing', '')

                            # remove multiple spaces and leading/trailing
                            form = re.sub('\s+', ' ', form).strip()

                            # skip over empty forms
                            if form == '-':
                                continue

                            # add lexeme to database
                            for row in ds.add_lexemes(
                                Language_ID=slug(lang['NAME']),
                                Parameter_ID=slug(english),
                                Value=form,
                                Source=['SatterthwaitePhillips2011'],
                            ):
                                pass

    def cmd_download(self, **kw):
        # the source file are the appendix of SP's thesis, converted with standard
        # `pdftotxt` tool (version 0.41.0; http://poppler.freedesktop.org);
        # data is from Appendix 1, pages 167-239
        self.raw.write('sources.bib', getEvoBibAsBibtex('SatterthwaitePhillips2011', **kw))
