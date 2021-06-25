# coding=UTF-8
'''
@Author: xiaoyichao
LastEditors: xiaoyichao
@Date: 2020-05-12 20:46:56
LastEditTime: 2021-06-25 16:08:05
@Description: 
'''
import numpy as np
import jieba
import Levenshtein
import time
import configparser
from sklearn.metrics.pairwise import cosine_similarity
from gensim.summarization import bm25
import os
import sys
os.chdir(sys.path[0])
sys.path.append("../")
from faq.get_question_vecs import ReadVec2bin
from faq.jieba4befaq import JiebaBEFAQ
from bert_server.sentence_bert_server import SentenceBERT


dir_name = os.path.abspath(os.path.dirname(__file__))
faq_config = configparser.ConfigParser()
faq_config.read(os.path.join(dir_name, "../config/befaq_conf.ini"))


class Matching(object):
    def __init__(self):
        self.read_vec2bin = ReadVec2bin()
        self.jiebaBEFAQ = JiebaBEFAQ()
        self.sentenceBERT = SentenceBERT()

    def cosine_sim(self, orgin_query, retrieval_questions, owner_name):
        '''
        @Author: xiaoyichao
        @param {type}
        @Description: BERT空间的余弦相似度
        '''
        sentences = self.read_vec2bin.read_bert_sents(owner_name=owner_name)
        bert_vecs = self.read_vec2bin.read_bert_vecs(owner_name=owner_name)
        orgin_query = orgin_query.replace("，", " ")
        orgin_query_list = orgin_query.split(' ')
        print("orgin_query_list", orgin_query_list)

        orgin_query_vec = self.sentenceBERT.get_bert(
            sentence_list=orgin_query_list)
        if orgin_query_vec != np.array([]):  # 如果BERT服务正常
            retrieval_questions_vec = []
            for retrieval_question in retrieval_questions:
                # 获取事先计算好的问题BERT 向量
                index_pos = sentences.index(retrieval_question)
                retrieval_question_vec = bert_vecs[index_pos]
                retrieval_question_vec = retrieval_question_vec.reshape(-1, 512)
                retrieval_questions_vec.append(retrieval_question_vec)

            retrieval_questions_vec = np.array(
                retrieval_questions_vec).reshape(-1, 512)

            # 计算出来的余弦相似度可能与理论值不一致，这是计算机存储机制导致的。通过四舍五入和异常处理，来规避异常数据出现在最后的结果中。
            sim_list = cosine_similarity(
                orgin_query_vec, retrieval_questions_vec)[0].tolist()

            # print('SKlearn:', end_time-begin_time)
            normalized_sim_list = []
            for sim in sim_list:
                if sim > 1.0:
                    sim = 1.0
                normalized_sim_list.append(sim)

            return normalized_sim_list
        else:  # 如果BERT服务超时了
            normalized_sim_list = []
            return normalized_sim_list

    def jaccrad(self, question, reference):  # reference为源句子，question为候选句子
        '''
        @Author: xiaoyichao
        @param {type}
        @Description: 计算两个句子的jaccard相似度
        '''
        terms_reference = jieba.cut(reference)  # 默认精准模式
        question = question.replace("\n", "")
        terms_model = jieba.cut(question)
        grams_reference = list(terms_reference)
        grams_model = list(terms_model)
        temp = 0
        for i in grams_reference:
            if i in grams_model:
                temp = temp+1
        fenmu = len(grams_model)+len(grams_reference)-temp  # 并集
        jaccard_coefficient = float(temp/fenmu)  # 交集
        return jaccard_coefficient

    def jaccard_sim(self, orgin_query, retrieval_questions):
        '''
        @Author: xiaoyichao
        @param {type}
        @Description: 计算query 和潜在问题的jaccard相似度
        '''
        sim_list = []
        for retrieval_question in retrieval_questions:
            jaccard_coefficient = self.jaccrad(
                question=orgin_query, reference=retrieval_question)
            sim_list.append(jaccard_coefficient)
        return sim_list

    def bm25_sim(self, orgin_query, retrieval_questions):
        '''
        @Author: xiaoyichao
        @param {type}
        @Description: 计算query 和潜在问题的BM25相似度
        '''
        jieba_corpus = []
        for corpu in retrieval_questions:
            line_seg = self.jiebaBEFAQ.get_list(corpu)
            jieba_corpus.append(line_seg)
        jieba_question = self.jiebaBEFAQ.get_list(orgin_query)
        bm25Model = bm25.BM25(jieba_corpus)
        sim_list = bm25Model.get_scores(jieba_question)
        normalized_sim_list = []
        max_sim = max(sim_list)
        for sim in sim_list:
            if sim == 0:
                normalized_sim = 0
            else:
                normalized_sim = sim/max_sim
            normalized_sim_list.append(normalized_sim)

        return normalized_sim_list

    def edit_distance_sim(self, orgin_query, retrieval_questions):
        '''
        @Author: xiaoyichao
        @param {type}
        @Description: 计算query 和潜在问题的编辑距离的相似度
        '''
        sim_list = []
        max_len = max(len(orgin_query), max([len(x) for x in retrieval_questions]))
        for corpu in retrieval_questions:
            edit_distance = Levenshtein.distance(orgin_query, corpu)
            sim = 1 - edit_distance * 1.0 / max_len
            sim_list.append(sim)
        return sim_list


if __name__ == "__main__":
    matching = Matching()
    question = "如何评价设计师"
    normalized_sim_list = matching.cosine_sim(
        question, ["如何评价设计师"], "领域1")
    print(normalized_sim_list)
