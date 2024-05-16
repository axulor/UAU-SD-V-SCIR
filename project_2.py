# -*- coding:utf-8 -*-
# Author：wangyc
# CreateTime：2023-04-16
# 修改本文件的cost_v参数可以得到在固定cost_v参数下，经一次博弈后的16次四个数据的取值，再对这16次数据取均值即可得在
# 固定cost_v，以及固定疫苗有效率下，某一R0值下的经一次博弈后的合作者变化情况
# 修改cost_v，或者修改疫苗有效率eff，可以研究其变化曲线以及不同的R0值组合


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
relative_path = Path("project_2-8c")
absolute_path = current_file_path / relative_path
os.makedirs(absolute_path, exist_ok=True)


# 定义参数
global_t = 1000


def calculate_type(epidemic_instance, e, init_c):
    US_D, AS_D, US_C, AS_C, AI, UR, AR, UV, AV = epidemic_instance.MMCA(T=40, init_u=0.99, init_c=init_c, init_i=0.02)

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


def calculate_delta_p_C(type_matrix, adjacency_matrix, transition_probabilities):
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
    num_nodes = len(type_matrix[0])
    updated_p_C = [0] * num_nodes

    for i in range(num_nodes):
        p_i_C = type_matrix[0][i] + type_matrix[1][i]  # 原始的p_i(C)概率
        updated_p_C[i] = p_i_C + delta_p_C[i]

    return updated_p_C



def get_transition_probabilities_tuple(cost_v, k):
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

def simulate(seed):

    # 创建双层网络
    lower_net = nx.barabasi_albert_graph(500, 5, seed=int(seed * np.random.rand() * 100))
    upper_net = Game.add_random_edges(lower_net, 200)

    # 创建传播实例
    Epidemic_sim = Epidemic.Epidemic(lower_net, upper_net, alpha=0.8, delta=0.2, beta=0.8333, eff=0.6, omega=0.2, eta=0.6,
                                     gamma=0.3333)
    # MMCA理论计算传播与博弈
    type_matrix = calculate_type(Epidemic_sim, e=Epidemic_sim.eff, init_c=0.1)
    print("MMCA理论计算传播后博弈前的合作者密度:", np.mean(type_matrix[0]) + np.mean(type_matrix[1]))
    adjacency_matrix = nx.to_numpy_array(upper_net)
    transition_probabilities = get_transition_probabilities_tuple(cost_v=0.3, k=0.1)
    delta_p_C = calculate_delta_p_C(type_matrix, adjacency_matrix, transition_probabilities)
    updated_p_C = calculate_updated_p_C(type_matrix, delta_p_C)
    print("MMCA理论计算的一次博弈后合作者密度:", np.mean(updated_p_C, axis=0))

    # MC模拟传播与博弈
    Game_sim = Game.Game(cost_v=0.3, lower_net=lower_net, upper_net=upper_net,
                         alpha=0.8, delta=0.2, beta=0.8333, eff=0.6, omega=0.2, eta=0.6, gamma=0.3333)
    n_iterations = 50
    total_pre_game_density = 0
    total_post_game_density = 0
    for iteration in range(n_iterations):
        Game_sim.init_awareness(init_u=0.99)
        Game_sim.init_strategy(init_c=0.1)
        Game_sim.init_state()
        Game_sim.init_infect(init_i=0.02)
        Game_sim.epidemic_mc(times=40)
        Game_sim.compute_payoff()
        pre_game_density = Game_sim.vc()
        total_pre_game_density += pre_game_density
        Game_sim.update_strategy(k=0.1)
        post_game_density = Game_sim.vc()
        total_post_game_density += post_game_density

    average_pre_game_density = total_pre_game_density / n_iterations
    average_post_game_density = total_post_game_density / n_iterations

    print("MC模拟的传播后博弈前的合作者密度（50次平均值）:", average_pre_game_density)
    print("MC模拟的一次博弈后合作者密度（50次平均值）:", average_post_game_density)

    return np.mean(type_matrix[0])+np.mean(type_matrix[1]), np.mean(updated_p_C, axis=0), average_pre_game_density, average_post_game_density


def main():
    seeds = [i for i in range(16)]
    eff = 0.6  # update this as needed
    with open(absolute_path / f"eff_{eff}.csv", 'w', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(["MMCA Pre-game", "MMCA Post-game", "MC Pre-game",
                         "MC Post-game"])  # header row
        for seed in seeds:
            results = simulate(seed)
            writer.writerow(results)

if __name__ == "__main__":
    main()








