import attr
import itertools
from pathlib import Path
import re

from clldutils import text
from clldutils.misc import slug
from pylexibank.dataset import Dataset as BaseDataset
from pylexibank import progressbar
from pylexibank import FormSpec


@attr.s
class FormSpecWithReplacement(FormSpec):
    replacements = attr.ib(default={}, validator=attr.validators.instance_of(dict))

    def clean(self, form, item=None):
        # make replacements first
        for s, t in sorted(
            self.replacements.items(), key=lambda x: len(x[0]), reverse=True
        ):
            form = form.replace(s, t)

        if form not in self.missing_data:
            if self.strip_inside_brackets:
                return text.strip_brackets(form, brackets=self.brackets)

            return form


class Dataset(BaseDataset):
    dir = Path(__file__).parent
    id = "satterthwaitetb"
    form_spec = FormSpecWithReplacement(
        separators=";/",
        brackets={"(": ")"},
        strip_inside_brackets=True,
        #        first_form_only=True,
        replacements={"= song": "", "= sing": "", "(ɨ)": "ɨ", "(y)": "y", "(r)": "r"},
    )

    def cmd_makecldf(self, args):
        # write the bibliographic sources
        args.writer.add_sources()

        # add languages
        language_lookup = args.writer.add_languages(lookup_factory="Name")

        # add the concepts from the concept list
        for concept in self.conceptlist.concepts.values():
            args.writer.add_concept(
                ID=slug(concept.label),
                Name=concept.english,
                Concepticon_ID=concept.concepticon_id,
                Concepticon_Gloss=concept.concepticon_gloss,
            )

        # Read the source diretly; the file was generated from a pdf2txt
        # conversion of the appendix of the thesis in question, and later
        # fixed with the fully documented code in raw/parse_pdf2txt.py
        # TODO: replace multiple spaces, strip
        for entry in self.raw_dir.read_csv("source.txt", delimiter="\t", dicts=True):
            args.writer.add_forms_from_value(
                Language_ID=language_lookup[entry["language"]],
                Parameter_ID=slug(entry["concept"]),
                Value=entry["value"],
                Source=["SatterthwaitePhillips2011"],
            )
