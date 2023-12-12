import logging
import random
import time
from datetime import timedelta

import comet
import torch
from sacrebleu.metrics import BLEU, CHRF
from tqdm import tqdm

from decoder import beam_search
from manager import Manager, Tokenizer

Logger = logging.Logger


def score_model(
    manager: Manager, tokenizer: Tokenizer, logger: Logger, use_tqdm: bool = False
) -> tuple[tuple, list[str]]:
    model, vocab = manager.model, manager.vocab
    assert manager.test and len(manager.test) > 0
    candidate, reference = [], []

    start = time.perf_counter()
    model.eval()
    with torch.no_grad():
        for batch in tqdm(manager.test, disable=(not use_tqdm)):
            src_nums, src_mask = batch.src_nums, batch.src_mask
            src_encs, tgt_nums = model.encode(src_nums, src_mask, batch.dict_mask), batch.tgt_nums
            for i in tqdm(range(src_encs.size(0)), leave=False, disable=(not use_tqdm)):
                out_nums = beam_search(manager, src_encs[i], src_mask[i], manager.beam_size)
                reference.append(tokenizer.detokenize(vocab.denumberize(tgt_nums[i].tolist())))
                candidate.append(tokenizer.detokenize(vocab.denumberize(out_nums.tolist())))
    elapsed = timedelta(seconds=(time.perf_counter() - start))

    bleu_score = BLEU().corpus_score(candidate, [reference])
    chrf_score = CHRF().corpus_score(candidate, [reference])

    samples = []
    tokenizer = Tokenizer(tokenizer.bpe, tokenizer.src_lang)
    for i, batch in enumerate(manager.test):
        for j, src_nums in enumerate(batch.src_nums):
            src_words = tokenizer.detokenize(vocab.denumberize(src_nums.tolist()))
            samples.append({'src': src_words, 'mt': candidate[i + j], 'ref': reference[i + j]})
    comet_model = comet.load_from_checkpoint(comet.download_model('Unbabel/wmt22-comet-da'))
    comet_score = comet_model.predict(samples)['system_score']

    checkpoint = f'BLEU = {bleu_score.score:.16f}'
    checkpoint += f' | CHRF = {chrf_score.score:.16f}'
    checkpoint += f' | COMET = {comet_score:.16f}'
    checkpoint += f' | Elapsed Time = {elapsed}'
    logger.info(checkpoint)

    return (bleu_score, chrf_score, comet_score), candidate


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--test', metavar='FILE', required=True, help='testing data')
    parser.add_argument('--model', metavar='FILE', required=True, help='model file (.pt)')
    parser.add_argument('--dict', metavar='FILE', required=False, help='dictionary data')
    parser.add_argument('--freq', metavar='FILE', required=False, help='frequency data')
    parser.add_argument('--lem-test', metavar='FILE', help='lemmatized testing data')
    parser.add_argument('--seed', type=int, help='random seed')
    parser.add_argument('--tqdm', action='store_true', help='progress bar')
    args, unknown = parser.parse_known_args()

    if args.seed:
        random.seed(args.seed)
        torch.manual_seed(args.seed)

    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    model_state = torch.load(args.model, map_location=device)

    config = model_state['model_config']
    for i, arg in enumerate(unknown):
        if arg[:2] == '--' and len(unknown) > i:
            option, value = arg[2:].replace('-', '_'), unknown[i + 1]
            try:
                config[option] = (int if value.isdigit() else float)(value)
            except ValueError:
                config[option] = value

    manager = Manager(
        model_state['src_lang'],
        model_state['tgt_lang'],
        config,
        device,
        args.model,
        model_state['vocab_list'],
        model_state['codes_list'],
        args.dict,
        args.freq,
        lem_data_file=None,
        lem_test_file=args.lem_test,
        data_file=None,
        test_file=args.test,
    )
    manager.model.load_state_dict(model_state['state_dict'])
    tokenizer = Tokenizer(manager.bpe, manager.src_lang, manager.tgt_lang)
    manager.test = manager.load_data(args.test, manager.lem_test, tokenizer)

    if device == 'cuda' and torch.cuda.get_device_capability()[0] >= 8:
        torch.set_float32_matmul_precision('high')

    logger = logging.getLogger('torch.logger')

    *_, candidate = score_model(manager, tokenizer, logger, args.tqdm)
    print('', *candidate, sep='\n')


if __name__ == '__main__':
    import argparse

    main()
