#!/bin/bash

echo "Performing Word Tokenization with Moses..."
sacremoses -l de -j 4 tokenize  < data/train.de > data/train.tokenized.de
sacremoses -l en -j 4 tokenize  < data/train.en > data/train.tokenized.en
echo "Done."

echo -e "\nLearning Model Vocab with BPE..."
cat data/train.tokenized.de data/train.tokenized.en | subword-nmt learn-bpe -s 10000 -o data/out
subword-nmt apply-bpe -c data/out < data/train.tokenized.de | subword-nmt get-vocab > data/vocab.de
subword-nmt apply-bpe -c data/out < data/train.tokenized.en | subword-nmt get-vocab > data/vocab.en
echo "Done."

echo -e "\nPerforming Subword Tokenization with BPE..."
subword-nmt apply-bpe -c data/out --vocabulary data/vocab.de --vocabulary-threshold 50 < data/train.tokenized.de > data/train.bpe.de
subword-nmt apply-bpe -c data/out --vocabulary data/vocab.en --vocabulary-threshold 50 < data/train.tokenized.en > data/train.bpe.en
echo "Done."

echo -e "\nCombining Source and Target Training Data..."
paste data/train.bpe.de data/train.bpe.en > data/train.bpe.de-en
echo "Done."
