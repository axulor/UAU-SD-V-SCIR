# -*- coding:utf-8 -*-
# Author：wangyc
# CreateTime：2023-04-16

import os
import Epidemic
import Game
import networkx as nx
import numpy as np
import copy
import pandas as pd
import math
import csv
import matplotlib.pyplot as plt
from multiprocessing import Pool
from pathlib import Path


# 创建项目文件夹
current_file_path = Path(__file__).parent
relative_path = Path("project_3_formal")
absolute_path = current_file_path / relative_path
os.makedirs(absolute_path, exist_ok=True)

# 定义超参数
global_t = 39
effective_t =30

def calculate_type(epidemic_instance, e, init_c=None, updated_p_C=None):
    '''
    计算传播结束时节点处在收益矩阵中的概率
    '''
    US_D, AS_D, US_C, AS_C, AI, UR, AR, UV, AV = epidemic_instance.MMCA(T=40, init_u=0.99, init_c=init_c,updated_p_C=updated_p_C ,init_i=0.02)

    # 获取节点个数
    cols = len(US_D[0])

    # 初始化type_matrix，使其具有与输入矩阵相同的维度
    type_matrix = [[0] * cols for _ in range(4)]

    # 计算每个节点的四种状态概率
    for i in range(cols):
        p_S_C = AS_C[-1][i] + US_C[-1][i]
        p_S_D = AS_D[-1][i] + US_D[-1][i]
        p_V = AV[-1][i] + UV[-1][i]
        p_R = AR[-1][i] + UR[-1][i]

        type_matrix[0][i] = (p_S_C + p_V)   # CH状态概率
        type_matrix[1][i] = (p_V / e) - (p_S_C + p_V)  # CNH状态概率
        type_matrix[2][i] = p_S_D  # DH状态概率
        type_matrix[3][i] = p_R - (p_V / e) + (p_S_C + p_V) # DNH状态概率

    return type_matrix


def get_transition_probabilities_tuple(cost_v, k):
    '''
    计算八种状态转移概率
    '''

    def get_payoff(state):
        if state == "CH":
            return -cost_v
        elif state == "CNH":
            return -(cost_v + 1)
        elif state == "DH":
            return 0
        elif state == "DNH":
            return -1

    states = ["DH", "CH", "CNH", "DNH"]
    transition_probabilities = {}

    for s_i in states:
        for s_j in states:
            payoff_diff = get_payoff(s_j) - get_payoff(s_i)
            transition_prob = 1 / (1 + math.exp(-payoff_diff / k))
            transition_probabilities[(s_i, s_j)] = transition_prob

    P_DH_CH = transition_probabilities[("DH", "CH")]
    P_DH_CNH = transition_probabilities[("DH", "CNH")]
    P_DNH_CH = transition_probabilities[("DNH", "CH")]
    P_DNH_CNH = transition_probabilities[("DNH", "CNH")]
    P_CH_DH = transition_probabilities[("CH", "DH")]
    P_CH_DNH = transition_probabilities[("CH", "DNH")]
    P_CNH_DH = transition_probabilities[("CNH", "DH")]
    P_CNH_DNH = transition_probabilities[("CNH", "DNH")]

    return (P_DH_CH, P_DH_CNH, P_DNH_CH, P_DNH_CNH, P_CH_DH, P_CH_DNH, P_CNH_DH, P_CNH_DNH)

def calculate_delta_p_C(type_matrix, adjacency_matrix, transition_probabilities):
    '''
    对每个节点计算策略选择转移概率
    '''
    P_DH_CH, P_DH_CNH, P_DNH_CH, P_DNH_CNH, P_CH_DH, P_CH_DNH, P_CNH_DH, P_CNH_DNH = transition_probabilities
    num_nodes = len(adjacency_matrix) # 返回邻接矩阵的行数
    delta_p_C = [0] * num_nodes

    for i in range(num_nodes):
        degree_i = sum(adjacency_matrix[i]) # i的度

        sum_DH = 0
        sum_DNH = 0
        sum_CH = 0
        sum_CNH = 0

        for j in range(num_nodes):
            if adjacency_matrix[i][j] == 1:
                sum_DH += (type_matrix[0][j] * P_DH_CH + type_matrix[1][j] * P_DH_CNH)
                sum_DNH += (type_matrix[0][j] * P_DNH_CH + type_matrix[1][j] * P_DNH_CNH)
                sum_CH += (type_matrix[2][j] * P_CH_DH + type_matrix[3][j] * P_CH_DNH)
                sum_CNH += (type_matrix[2][j] * P_CNH_DH + type_matrix[3][j] * P_CNH_DNH)

        delta_p_C[i] = (type_matrix[2][i] / degree_i) * sum_DH + (type_matrix[3][i] / degree_i) * sum_DNH \
                       - (type_matrix[0][i] / degree_i) * sum_CH - (type_matrix[1][i] / degree_i) * sum_CNH

    return delta_p_C

def calculate_updated_p_C(type_matrix, delta_p_C):
    '''
    每个节点执行策略转移
    '''
    num_nodes = len(type_matrix[0])
    updated_p_C = [0] * num_nodes

    for i in range(num_nodes):
        p_i_C = type_matrix[0][i] + type_matrix[1][i]  # 原始的p_i(C)概率
        updated_p_C[i] = p_i_C + delta_p_C[i]

    return updated_p_C


def save_results_to_file(data, filename):
    '''
    保存计算的数据
    '''
    df = pd.DataFrame(data)
    if os.path.isfile(filename):
        df_old = pd.read_csv(filename, header=None)
        df_new = pd.concat([df_old, df], axis=1, ignore_index=True)
    else:
        df_new = df
    df_new.to_csv(filename, index=False, header=False)

def simulate(seed):
    lower_net = nx.barabasi_albert_graph(500, 5, seed=int(seed * np.random.rand() * 100))
    upper_net = Game.add_random_edges(lower_net, 200)

    Epidemic_sim = Epidemic.Epidemic(lower_net, upper_net, alpha=0.6, delta=0.4, beta=0.8333, eff=0.10, omega=0.1, eta=0.6,
                                     gamma=0.3333)

    filename = str(absolute_path / 'MMCA_t_cost_v0.7-eff0.10.csv')  # Define the path of the file.
    results = []  # Initialize an empty list to collect the results.

    for t in range(global_t):
        if t == 0:
            type_matrix = calculate_type(Epidemic_sim, e=Epidemic_sim.eff, init_c=0.1) # 计算状态分布矩阵
            print("MMCA理论计算传播后博弈前的合作者密度:", np.mean(type_matrix[0]) + np.mean(type_matrix[1]))
            results.append( [np.mean(type_matrix[0]) + np.mean(type_matrix[1])])

            adjacency_matrix = nx.to_numpy_array(upper_net)
            transition_probabilities = get_transition_probabilities_tuple(cost_v=0.7, k=0.1)
            delta_p_C = calculate_delta_p_C(type_matrix, adjacency_matrix, transition_probabilities)
            updated_p_C = calculate_updated_p_C(type_matrix, delta_p_C)
            mean_updated_p_C = np.mean(updated_p_C, axis=0)
            results.append([mean_updated_p_C])
            print("MMCA理论计算的一次博弈后合作者密度:", mean_updated_p_C)
        else:
            type_matrix = calculate_type(Epidemic_sim, e=Epidemic_sim.eff, updated_p_C=updated_p_C)
            print("MMCA理论计算传播后博弈前的合作者密度:", np.mean(type_matrix[0]) + np.mean(type_matrix[1]))
            adjacency_matrix = nx.to_numpy_array(upper_net)
            transition_probabilities = get_transition_probabilities_tuple(cost_v=0.7, k=0.1)
            delta_p_C = calculate_delta_p_C(type_matrix, adjacency_matrix, transition_probabilities)
            updated_p_C = calculate_updated_p_C(type_matrix, delta_p_C)
            mean_updated_p_C = np.mean(updated_p_C, axis=0)
            results.append([mean_updated_p_C])
            print("MMCA理论计算的一次博弈后合作者密度:", mean_updated_p_C)

    save_results_to_file(results, filename)

if __name__ == '__main__':
    simulate(1)

