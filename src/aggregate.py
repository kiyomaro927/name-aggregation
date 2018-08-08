"""Aggregate name by the repname."""
import argparse
import datetime
import re

import progressbar
import zenhan
from pyknp import Jumanpp


def count_line(path):
    """

    :param path: path to input file
    :return: the line number of line

    """
    with open(path) as f:
        return len([_ for _ in f])


def load_file(path):
    """

    :param path: path to input file
    :return: data in the file

    """
    n_line = count_line(path)
    bar = progressbar.ProgressBar()
    with open(path) as f:
        return [word.strip() for word in bar(f, max_value=n_line)]


def preprocess_word(words):
    """

    :param words: a list of words to be preprocessed
    :return: preprocessed word

    """
    return [zenhan.h2z(word) for word in words]


def kansuji2arabic(kstring):
    """

    :param kstring: word which indicates a number
    :return: word represented by Arabic numerals

    """
    # https://qiita.com/cof/items/58ddf898db25db561a54
    tt_ksuji = str.maketrans('一二三四五六七八九〇壱弐参', '1234567890123')
    re_suji = re.compile(r'[十拾百千万億兆\d]+')
    re_kunit = re.compile(r'[十拾百千]|\d+')
    re_manshin = re.compile(r'[万億兆]|[^万億兆]+')
    TRANSUNIT = {
        '十': 10,
        '拾': 10,
        '百': 100,
        '千': 1000
    }
    TRANSMANS = {
        '万': 10000,
        '億': 100000000,
        '兆': 1000000000000
    }

    def _transvalue(sj, re_obj=re_kunit, transdic=TRANSUNIT):
        unit = 1
        result = 0
        for piece in reversed(re_obj.findall(sj)):
            if piece in transdic:
                if unit > 1:
                    result += unit
                unit = transdic[piece]
            else:
                val = int(piece) if piece.isdecimal() else _transvalue(piece)
                result += val * unit
                unit = 1

        if unit > 1:
            result += unit

        return result

    transuji = kstring.translate(tt_ksuji)
    for suji in sorted(set(re_suji.findall(transuji)), key=lambda s: len(s), reverse=True):
        if not suji.isdecimal():
            arabic = _transvalue(suji, re_manshin, TRANSMANS)
            arabic = str(arabic)
            transuji = transuji.replace(suji, arabic)

    return zenhan.h2z(transuji)


def get_repname_set(words):
    """

    :param words: words in input file
    :return: a list of sets of representative names for the words

    """
    n_word = len(words)
    juman = Jumanpp()
    bar = progressbar.ProgressBar()
    repname_sets = []
    for word in bar(words, max_value=n_word):
        repname_set = []
        r = juman.analysis(word)
        for mrph in r.mrph_list():
            if mrph.bunrui == '数詞':
                repname_set.append(tuple(kansuji2arabic(mrph.midasi)))
            elif mrph.repnames() != '':
                repname_set.append(tuple(mrph.repnames().split('?')))
            else:
                repname_set.append(tuple([mrph.midasi]))
        repname_sets.append(expand_ambiguity(repname_set))
    return repname_sets


def expand_ambiguity(repname):
    """

    :param repname: a list of tuples which include the repname candidates for morphemes
    :return: a list of repname candidates for morphemes

    """
    def product_tuple(t1, t2):
        return tuple([_t1 + _t2 for _t1 in t1 for _t2 in t2])

    expanded_repname = tuple([''])
    for _repname in repname:
        expanded_repname = product_tuple(expanded_repname, _repname)
    return expanded_repname


def aggregate(words, repname_sets):
    """

    :param words: words in input file
    :param repname_sets: a list of sets of representative names for the words
    :return: words with aggregated ID

    """
    # TODO: Access ConceptNet to retrieve `Sysnonym` and `FormOf` of words
    # build a list of set to be merged
    repname_sets_to_merge = [set(repname_sets[0])]
    for repname_set in repname_sets[1:]:
        repname_set = set(repname_set)
        for i, repname_set_to_merge in enumerate(repname_sets_to_merge):
            if len(repname_set & repname_set_to_merge) > 0:
                repname_sets_to_merge[i] = repname_set | repname_set_to_merge
                break
        else:
            repname_sets_to_merge.append(repname_set)

    # assign IDs for each set
    repname2id = {}
    for i, repname_set in enumerate(repname_sets_to_merge):
        for repname in repname_set:
            repname2id[repname] = i

    # assign IDs to words
    word_with_id = []
    for word, repname_set in zip(words, repname_sets):
        repname = repname_set[0]
        word_with_id.append((word, repname2id[repname]))
    return word_with_id


def save(path, out):
    """

    :param path: path to output file
    :param out: words with ID

    """
    with open(path, 'w') as f:
        for word, id in out:
            f.write('{}\t{}\n'.format(word, id))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('IN', help='path to input file')
    parser.add_argument('OUT', help='path to output file')
    args = parser.parse_args()

    print('[{}] Loading data... '.format(datetime.datetime.now()))
    words = load_file(args.IN)
    prerprocessed_words = preprocess_word(words)

    print('[{}] Getting repname for data... '.format(datetime.datetime.now()))
    repname_sets = get_repname_set(prerprocessed_words)

    print('[{}] Aggregating words... '.format(datetime.datetime.now()))
    out = aggregate(words, repname_sets)
    save(args.OUT, out)


if __name__ == '__main__':
    main()
