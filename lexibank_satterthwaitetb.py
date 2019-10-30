import attr
import itertools
from pathlib import Path
import re

from clldutils.misc import slug
from pylexibank.dataset import Dataset as BaseDataset
from pylexibank.util import progressbar

ERRATA = {
    "earth": {"repl": "earth1|earth2", "num_tokens": 2},
    "enter （去）[": {
        "repl": "enter|evening|extinguish|eye|fall|Hanzi|徃 (去) [徃来]",
        "num_tokens": 7,
    },
    "far": {
        "repl": "far|fart, to|fast|fat [of person]|fat [of meat]|father|fear, to|Hanzi|径",
        "num_tokens": 8,
    },
    "hard": {
        "repl": "hard|hate1|hate2|he|head|hear|Hanzi|硬|恨|讨厌（人）|他|头|听见|Pinyin",
        "num_tokens": 15,
    },
    "insect": {
        "repl": "insect|inside|itchy|joint|jump|kick|kidney|Hanzi|虫子|里面|痒|关节|跳|踢|肾",
        "num_tokens": 13,
    },
    "medicine": {"repl": "medicine|mend (clothes)|metal|milk|monkey", "num_tokens": 4},
    "shadow": {
        "repl": "shadow|shallow|sharp1|sharp2|she|sheep|Hanzi|影子|浅|(刀) 快|锋利|她|羊|Pinyin|ying zi30|qian3|(dao) kuai14|feng li14|ta1|yang2|Baihong|a31 ba31 la55 sɤ55|de55|-|da55|a31 jo31|a55 dzɨ31",
        "num_tokens": 28,
    },
    "saliva": {
        "repl": "saliva|squeeze|stand up|star|steal|Hanzi|口水|压榨|站|星星|䫖",
        "num_tokens": 9,
    },
    "swell": {
        "repl": "swell|swim|tail|tall (of stature)|taste|ten|that|Hanzi|肿",
        "num_tokens": 8,
    },
    "wash": {
        "repl": "wash|water|wax gourd|wax|weave|Hanzi|洗|水|冬瓜|蜡|编织 [织(布)]|Pinyin|xi3|shui3|dong gua11|la4|bian zhi11|Baihong",
        "num_tokens": 19,
    },
}

# dictionary for the number of elements to remove at the end of the lists,
# using the first English word in each list/page as index; by default only
# the last element, the page number, will be removed, but some pages have
# garbage characters and/or footnotes that need to be treated with these
# exceptions
DROP_FINAL = {
    "hard": 3,
    "insect": 2,
    "man": 2,
    "medicine": 4,
    "palm": 4,
    "shadow": 3,
    "saliva": 2,
    "wash": 3,
    "wood": 2,
}

ROW_IDX = {
    "concepts": (None, "Hanzi"),
    "Hanzi": ("Hanzi", "Pinyin"),
    "Mandarin": ("Pinyin", "Baihong"),
    "Baihong": ("Baihong", "Biyue"),
    "Biyue": ("Biyue", "Hani"),
    "Hani": ("Hani", "Jinghpo"),
    "Jinghpo": ("Jinghpo", "Jinuo"),
    "Jinuo": ("Jinuo", "Kucong"),
    "Kucong": ("Kucong", "Lahu Na"),
    "Lahu Na": ("Lahu Na", "Lahu Shi"),
    "Lahu Shi": ("Lahu Shi", "Lisu"),
    "Lisu": ("Lisu", "Nasu"),
    "Nasu": ("Nasu", "Naxi"),
    "Naxi": ("Naxi", "Nisu"),
    "Nisu": ("Nisu", "Nosu"),
    "Nosu": ("Nosu", "Nusu"),
    "Nusu": ("Nusu", "Samei"),
    "Samei": ("Samei", "Zaiwa"),
    "Zaiwa": ("Zaiwa", "Zaozou"),
    "Zaozou": ("Zaozou", None),
}


class Dataset(BaseDataset):
    dir = Path(__file__).parent
    id = "satterthwaitetb"

    def _read_page_data(self):
        # The raw data for this dataset is a bit complex to process, with
        # all the common quircks. It is separated in pages which need to
        # be cleaned and joined, besides being distributed in lines which
        # need manual corrections. The information is found in "cells",
        # which need form cleaning and also carry some superfluous
        # information, such as invisible Unicode characters.
        # In this first block of code, we read the raw lines and work
        # around structure problems, leaving the data in the state it
        # would be for an appropriate raw data (form cleaning is
        # performed when adding the data).
        lines = self.raw_dir.read("phillips-tibeto-burman-data.txt").split("\n")

        # Group lines into pages with a list comprehension that matches
        # entries equal to "English" or "\x0cEnglish", the
        # first entry at the top of each page in the source. Items are then
        # groups, resulting in a structure similar to a .split() on an
        # entire file.
        pages = [
            list(g)
            for k, g in itertools.groupby(
                lines, lambda x: x in ["English", "\x0cEnglish"]
            )
            if not k
        ]

        # The grouping login above works reasonably well, but there are some
        # errors due to problems in the source (such as multiple newlines).
        # We can correct most of them with a simple test: as the table lines
        # are read as empty strings, whener we have two onn empty entries
        # we should join them.
        page_data = []
        for page in pages:
            # Collect the cells for the current page (doing in dumb nested
            # loops, so it is easier to read than a list comprehension)
            page_cells = [page[0]]
            for cell in page[1:]:
                if page_cells[-1] and cell:
                    page_cells[-1] = "%s %s" % (page_cells[-1], cell)
                else:
                    page_cells.append(cell)

            # remove empty lists, so it's easy to fix PDF conversion
            # errors (which likely mirrors the order the author edited his
            # Word source...) and we can refer to a page by its first
            # English gloss
            page_cells = [cell for cell in page_cells if cell]

            # If the first entry in `page_cells` matches one of the
            # problematic entries listed in the `ERRATA` (mostly cases
            # where the order in the raw data is not the one found in
            # the printed material, such as swapped entries likely due to
            # PDF conversion), replace a number of cells in `page_cells`
            # (as specificed in the same errata)
            if page_cells[0] in ERRATA:
                page_cells = (
                    ERRATA[page_cells[0]]["repl"].split("|")
                    + page_cells[ERRATA[page_cells[0]]["num_tokens"] :]
                )

            # Replaces FULLWIDTH PARENTHESIS with normal ones and strip all
            # cells; for debugging purposes, it is better to do it manually
            # here, instead than treating it with a profile (some terminals
            # and typefaces don't even render the fullwidth paranthesis
            # differently)
            page_cells = [cell.replace("）", ")") for cell in page_cells]

            # At this point, all page cells still contain some trailing
            # elements with superflouos information, such as the page number or
            # footnotes. Given that they are not found in all pages
            # in the same number when found, once more we need a manual
            # correction. If the the first cell of the page is not listed
            # in the `DROP_FINAL` exceptions, we default to removing only
            # the last element
            page_cells = page_cells[: -DROP_FINAL.get(page_cells[0], 1)]

            # Once more due the PDF correction, in some cases the contents
            # are shifted one entry to left due to empty cells. As the number
            # of such empty cells changes from page to page, we need to
            # test the rows, by index, to make sure the data is there.
            page_rows = {}
            for row_name, indexes in ROW_IDX.items():
                if not indexes[0]:  # concept, first one
                    idx2 = page_cells.index(indexes[1])
                    row = page_cells[:idx2]
                elif not indexes[1]:  # Zaozou, last one
                    idx1 = page_cells.index(indexes[0])
                    row = page_cells[idx1:]
                else:
                    idx1 = page_cells.index(indexes[0])
                    idx2 = page_cells.index(indexes[1])
                    row = page_cells[idx1:idx2]

                # In all cases except the concept row, exclude the first
                # element (it is the language name, we already have it)
                if row_name is not "concepts":
                    page_rows[row_name] = row[1:]
                else:
                    page_rows[row_name] = row

            # Finally collect the page data
            page_data.append(page_rows)

        return page_data

    def cmd_makecldf(self, args):
        # read page data, solving all PDF conversion problems (forms still
        # need to be cleaned)
        page_data = self._read_page_data()

        # write the bibliographic sources
        args.writer.add_sources()

        # add the languages from the language list
        for language in self.languages:
            args.writer.add_language(
                ID=slug(language["Name"]),
                Name=language["Name"],
                Glottocode=language["Glottocode"],
                Glottolog_Name=language["Glottolog_Name"],
            )

        # add the concepts from the concept list
        # TODO: add `English` and other fields?
        for concept in self.conceptlist.concepts.values():
            args.writer.add_concept(
                ID=slug(concept.label),
                Concepticon_ID=concept.concepticon_id,
                Concepticon_Gloss=concept.concepticon_gloss,
            )

        for page in progressbar(page_data):
            # for each concept...
            for idx, english in enumerate(page["concepts"]):
                for lang in page.keys():
                    if lang in ["concepts", "Hanzi"]:
                        continue
                    # extract the value (raw transcription) and apply
                    # some initial correction before splitting into the
                    # various forms; before removing parentheses, we
                    # manually correct and preserve the few cases in which
                    # the parentheses are actual sound information and
                    # not comments
                    value = page[lang][idx]
                    value = value.replace("(y)", "y")
                    value = value.replace("(r)", "r")
                    value = value.replace("(ɨ)", "ɨ")
                    #                    value = strip_brackets(value, brackets={"(": ")"})

                    for form in value.split(";"):
                        #                    for form in split_text(value, separators=";/"):
                        # correct forms with glosses without parentheses
                        form = form.replace("= song", "")
                        form = form.replace("= sing", "")

                        # remove multiple spaces and leading/trailing
                        form = re.sub(r"\s+", " ", form).strip()

                        # skip over empty forms
                        if form == "-":
                            continue

                        # add lexeme to database
                        args.writer.add_form(
                            Language_ID=slug(lang),
                            Parameter_ID=slug(english),
                            Value=form,
                            Form=form,
                            Source=["SatterthwaitePhillips2011"],
                        )
