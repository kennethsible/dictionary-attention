import json
import os
import re

from subword_nmt.apply_bpe import BPE
from tqdm import tqdm

from translation.manager import Tokenizer

filters = [
    r'\([^\)]+\)',
    r'\[[^\]]+\]',
    r'\{[^\}]+\}',
    r'<[^>]+>',
]

abbrs = [
    r'etw\.',
    r'jdm\.',
    r'jdn\.',
    r'jds\.',
]

preps = [
    'in',
    'neben',
    'hinter',
    'vor',
    'an',
    'auf',
    'über',
    'unter',
    'zwischen',
    'aus',
    'außer',
    'bei',
    'mit',
    'nach',
    'seit',
    'von',
    'zu',
    'bis',
    'durch',
    'für',
    'ohne',
    'gegen',
    'um',
    'statt',
    'trotz',
    'während',
    'wegen',
]

for prep in preps:
    for abbr1 in abbrs:
        for abbr2 in abbrs:
            filters.append(f'{prep} {abbr1}/{abbr2}')
for prep in preps:
    for abbr in abbrs:
        filters.append(f'{prep} {abbr}')
for abbr1 in abbrs:
    for abbr2 in abbrs:
        filters.append(f'{abbr1}/{abbr2}')
filters.extend(abbrs)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--data-dir', required=True, help='output directory')
    args = parser.parse_args()
    url = 'https://ftp.tu-chemnitz.de/pub/Local/urz/ding/de-en-devel/de-en.txt.gz'
    os.system(f'wget -q -P {args.data_dir} {url} --show-progress')

    with open(f'{args.data_dir}/codes.tsv') as codes_file:
        tokenizer = Tokenizer(BPE(codes_file), 'en')

    deen_dict = {}
    with open(f'{args.data_dir}/de-en.txt') as dict_file:
        for line in tqdm(dict_file.readlines()):
            if line.startswith('#'):
                continue
            line = re.sub('|'.join(filters), '', line)
            line = re.sub(r'\s+', ' ', line)
            de, en = line.split('::')
            for words, defns in zip(de.split('|'), en.split('|')):
                for headword in words.split(';'):
                    headword = headword.strip()
                    if not headword.replace('-', '').isalpha():
                        continue
                    headword = re.sub(r'^sich ', '', headword)
                    for definition in defns.split(';'):
                        definition = definition.strip()
                        if headword == definition:
                            continue
                        definition = tokenizer.tokenize(definition)
                        if not definition:
                            continue
                        if headword not in deen_dict:
                            deen_dict[headword] = []
                        if definition not in deen_dict[headword]:
                            deen_dict[headword].append(definition)

    with open(f'{args.data_dir}/de-en.json', 'w') as dict_file:
        deen_dict = dict(sorted(deen_dict.items(), key=lambda x: x[0]))
        json.dump(deen_dict, dict_file, indent=4, ensure_ascii=False)
    print(len(deen_dict), f'{args.data_dir}/de-en.json')


if __name__ == '__main__':
    import argparse

    main()
