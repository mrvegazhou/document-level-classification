# coding=utf-8
"""
Author  : Jane
Contact : xijian@ict.ac.cn
Time    : 2021/2/5 12:47
Desc:

https://torchtext.readthedocs.io/en/latest/vocab.html#vocab

"""
import pandas as pd
import re
import jieba
from collections import Counter
from tqdm import tqdm
import pickle
import os

import torch
import torchtext

import sys
sys.path.append('/home/xijian/pycharm_projects/document-level-classification/')
from dpcnn.config import *


df_stopwords = pd.read_csv(stopwords_file, index_col=False, quoting=3, sep="\t", names=['stopword'], encoding='utf-8')
# quoting：控制引用字符引用行为，QUOTE_MINIMAL (0), QUOTE_ALL (1), QUOTE_NONNUMERIC (2) or QUOTE_NONE (3).
STOPWORDS_SET = set(df_stopwords['stopword'].values)

# 读取数据  数据格式：content    label
def read_data(filepath):
    df_data = pd.read_csv(filepath, encoding='UTF-8', sep='\t', names=['label', 'content'], index_col=False)
    df_data = df_data.dropna()
    print(df_data.head())

    x_data, y_data = df_data['content'], df_data['label']
    print('*'*27, x_data.shape, len(x_data[0]), y_data.shape)  # (50000,) 746 (50000,)

    y_data = [label2id[y] for y in y_data]
    # y_data = torch.tensor(y_data, dtype=torch.long)

    return x_data, y_data


# 保留文本中文、数字、英文、短横线
def clear_text(text):
    p = re.compile(r"[^\u4e00-\u9fa5^0-9^a-z^A-Z\-、，。！？：；（）《》【】,!\?:;[\]()]")  # 匹配不是中文、数字、字母、短横线的部分字符
    return p.sub('', text)  # 将text中匹配到的字符替换成空字符


# 分词
def tokenize(text):
    text = clear_text(text) # 文本清洗
    segs = jieba.lcut(text.strip(), cut_all=False)  # cut_all=False是精确模式，True是全模式；默认模式是False 返回分词后的列表
    segs = filter(lambda x: len(x.strip()) > 1, segs)  # 词长度要>1，没有保留标点符号
    segs = filter(lambda x: x not in STOPWORDS_SET, segs) # 去除停用词 segs是一个filter object
    return list(segs)


# 过滤低频词
def filter_lowfreq_words(arr, vocab):
    # arr是一个batch，以list的形式出现，list长度=batchsize，list中每个元素是长度=MAX_LEN的句子，句子已经分词，词已经转化为index
    arr = [[x if x < total_words else 0 for x in example] for example in arr]  # 词的ID是按频率降序排序的 <unk>=0
    return arr


# 顺序：tokenize分词，preprocessing，建立词表build vocab，batch（padding & truncate to maxlen），postprocessing
TEXT = torchtext.data.Field(sequential=True,
                            tokenize=tokenize,
                            fix_length=doc_maxlen,
                            # preprocessing=, # after tokenizing but before numericalizing
                            postprocessing=filter_lowfreq_words # after numericalizing but before the numbers are turned into a Tensor
                            )
LABEL = torchtext.data.Field(sequential=False,
                             use_vocab=False
                             )

def get_dataset(inp, lab):
    fields = [('inp', TEXT), ('lab', LABEL)]  # filed信息 fields dict[str, Field])
    examples = []  # list(Example)
    for inp, lab in tqdm(zip(inp, lab)): # 进度条
        # 创建Example时会调用field.preprocess方法
        examples.append(torchtext.data.Example.fromlist([inp, lab], fields))
    return examples, fields


class DataLoader:
    def __init__(self, data_iter):
        self.data_iter = data_iter
        self.length = len(data_iter)  # 一共有多少个batch？

    def __len__(self):
        return self.length

    def __iter__(self):
        # 注意，在此处调整text的shape为batch first，并调整label的shape和dtype
        for batch in self.data_iter:
            yield (torch.transpose(batch.inp, 0, 1), batch.lab.long())  # label->long



def load_data(data_path, traindata=False, shuffle=False):
    x_data, y_data = read_data(data_path)

    ds = torchtext.data.Dataset(*get_dataset(x_data, y_data))
    # 查看1个样本的信息
    print('*'*27, len(ds[0].inp), len(ds[1].inp), ds[0].inp, ds[0].lab) #182 402 ['马晓旭', '意外', '受伤', ...

    if os.path.exists(counter_path):
        print('计数器存在!')
        with open(counter_path, 'rb') as handle:
            c = pickle.load(handle)
        TEXT.vocab = torchtext.vocab.Vocab(c, max_size=total_words)
    else:
        print('计数器不存在!')
        TEXT.build_vocab(ds, max_size=total_words)
        with open(counter_path, 'wb') as handle:  # 可用于infer阶段
            # 构建一个{词：词频}的字典，并持久化存储，未来用于build vocab 处理文本数据，将文本转化为Index
            pickle.dump(TEXT.vocab.freqs, handle)
    print('*' * 27, '词表大小:', len(TEXT.vocab))

    ds_iter = torchtext.data.Iterator(ds,
                                      batch_size,
                                      # sort_key=lambda x: len(x.inp),
                                      # device=,
                                      train=traindata,
                                      # repeat=,
                                      shuffle=shuffle,
                                      sort=False,
                                      # sort_within_batch=,
                                      )
    data_loader = DataLoader(ds_iter)
    return data_loader


if __name__=='__main__':
    train_dataloader = load_data(data_base_dir + 'cnews.train.txt', traindata=True, shuffle=True)
    val_dataloader = load_data(data_base_dir + 'cnews.val.txt', traindata=False, shuffle=False)

    print('*' * 27, 'len(train_dataloader):', len(train_dataloader))  # 1000 个step/batch
    for batch_text, batch_label in train_dataloader:
        print(batch_text.shape, batch_label.shape)  # [b,500], [b]
        # print(batch_text[0])
        print(batch_label[0], batch_label[0].dtype) # tensor(5) torch.int64
        break