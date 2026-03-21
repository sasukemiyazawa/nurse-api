# 起動に必要なモジュールのインストール
# pip install -r requirements.txt

# 起動コマンド uvicorn main:app --reload

from fastapi import FastAPI, Form, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel, EmailStr
from starlette.responses import JSONResponse
import pulp
from typing import List
import os
import random
import asyncio
from uuid import uuid4

import numpy as np
import time
import json
from deap import base, creator, tools, algorithms


app = FastAPI()

# ✅ 修正①: app.state.jobs を起動時に初期化
app.state.jobs = {}

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],  # ✅ set → list に修正（{"*"} はエラーの原因になる場合あり）
)


# -------------------------------------------------------
# GAの非同期+ステータス管理の実装
# -------------------------------------------------------

@app.post("/ga/start")
async def start_ga(gen: int = Form(), firstday: int = Form(0)):
    # ✅ 修正②: gen パラメータを追加、firstday はデフォルト0
    job_id = str(uuid4())
    app.state.jobs[job_id] = {"status": "running", "progress": 0, "result": None}

    # ✅ 修正③: run_ga を定義して create_task に渡す
    asyncio.create_task(run_ga(job_id, gen, firstday))

    return {"job_id": job_id}


@app.get("/ga/status/{job_id}")
async def get_status(job_id: str):
    if job_id not in app.state.jobs:
        return {"error": "job not found"}
    return app.state.jobs[job_id]


@app.get("/ga/result/{job_id}")
async def get_result(job_id: str):
    if job_id not in app.state.jobs:
        return {"error": "job not found"}
    return app.state.jobs[job_id].get("result")


# ✅ 修正④: run_ga を定義（GAをスレッドで実行し、進捗をstateに書き込む）
async def run_ga(job_id: str, gen: int, firstday: int):
    try:
        loop = asyncio.get_event_loop()
        # GAはCPUバウンドなのでスレッドプールで実行（メインスレッドをブロックしない）
        await loop.run_in_executor(None, lambda: ga(job_id, gen, firstday))
        app.state.jobs[job_id]["status"] = "done"
    except Exception as e:
        app.state.jobs[job_id]["status"] = "error"
        app.state.jobs[job_id]["error"] = str(e)
        print(f"GA error: {e}")


# -------------------------------------------------------
# GA本体（進捗更新つき）
# -------------------------------------------------------

def ga(job_id: str, gen: int, firstday: int = 0):
    NUM_NURSES = 10
    DAYS = 31
    MAX_WORKING_DAYS = 20
    MAX_NIGHT_SHIFTS = 5

    # DEAPのクラスは重複登録するとエラーになるため確認してから作成
    if not hasattr(creator, "FitnessMin"):
        creator.create("FitnessMin", base.Fitness, weights=(-1.0,))
    if not hasattr(creator, "Individual"):
        creator.create("Individual", np.ndarray, fitness=creator.FitnessMin)

    def evaluate(individual):
        individual = np.array(individual).reshape(NUM_NURSES, DAYS)
        penalty = 0
        for nurse in range(NUM_NURSES):
            working_days = np.sum(individual[nurse] > 0)
            night_shifts = np.sum(individual[nurse] == 2)
            if working_days > MAX_WORKING_DAYS:
                penalty += (working_days - MAX_WORKING_DAYS) * 10
            if night_shifts > MAX_NIGHT_SHIFTS:
                penalty += (night_shifts - MAX_NIGHT_SHIFTS) * 10
            for day in range(DAYS):
                if individual[nurse][day] == 2 and day + 1 < DAYS:
                    if individual[nurse][day + 1] != 0:
                        penalty += 10

        for day in range(DAYS):
            weekday = (firstday + day) % 7
            is_weekend = (weekday == 0 or weekday == 6)
            day_shift = np.sum(individual[:, day] == 1)
            night_shift = np.sum(individual[:, day] == 2)
            if is_weekend:
                penalty += abs(day_shift - 2) * 10
            else:
                penalty += abs(day_shift - 6) * 10
            penalty += abs(night_shift - 1) * 10

        return penalty,

    toolbox = base.Toolbox()
    toolbox.register("attr_gene", random.randint, 0, 2)
    toolbox.register("individual", tools.initRepeat, creator.Individual,
                     toolbox.attr_gene, NUM_NURSES * DAYS)
    toolbox.register("population", tools.initRepeat, list, toolbox.individual)
    toolbox.register("evaluate", evaluate)
    toolbox.register("mate", tools.cxUniform, indpb=0.5)
    toolbox.register("mutate", tools.mutUniformInt, low=0, up=2, indpb=0.2)
    toolbox.register("select", tools.selTournament, tournsize=3)

    random.seed(int(time.time()))

    N_GEN = gen
    POP_SIZE = 5000
    CX_PB = 0.9
    MUT_PB = 0.2

    pop = toolbox.population(n=POP_SIZE)

    # 評価（第0世代）
    fitnesses = list(map(toolbox.evaluate, pop))
    for ind, fit in zip(pop, fitnesses):
        ind.fitness.values = fit

    # ✅ 世代ごとに進捗を更新しながら進化
    for generation in range(1, N_GEN + 1):
        offspring = toolbox.select(pop, len(pop))
        offspring = list(map(toolbox.clone, offspring))

        for child1, child2 in zip(offspring[::2], offspring[1::2]):
            if random.random() < CX_PB:
                toolbox.mate(child1, child2)
                del child1.fitness.values
                del child2.fitness.values

        for mutant in offspring:
            if random.random() < MUT_PB:
                toolbox.mutate(mutant)
                del mutant.fitness.values

        invalid_ind = [ind for ind in offspring if not ind.fitness.valid]
        fitnesses = map(toolbox.evaluate, invalid_ind)
        for ind, fit in zip(invalid_ind, fitnesses):
            ind.fitness.values = fit

        pop[:] = offspring

        # 進捗を更新（0〜100%）
        progress = int((generation / N_GEN) * 100)
        app.state.jobs[job_id]["progress"] = progress
        print(f"Generation {generation}/{N_GEN} - progress: {progress}%")

    best_ind = tools.selBest(pop, 1)[0]
    schedule = np.array(best_ind).reshape(NUM_NURSES, DAYS)

    # 結果を辞書に変換
    dic = {}
    for i in range(NUM_NURSES):
        buff = []
        for j in range(DAYS):
            if schedule[i][j] == 0:
                buff.append("/")
            elif schedule[i][j] == 1:
                buff.append("D")
            elif schedule[i][j] == 2:
                buff.append("N")
        dic[f'ナース{i+1}'] = buff

    # 横の集計（各ナースの日勤・夜勤数）
    lD, lN = [], []
    for i in range(NUM_NURSES):
        lD.append(int(np.sum(schedule[i] == 1)))
        lN.append(int(np.sum(schedule[i] == 2)))

    # 縦の集計（各日の日勤・夜勤人数）
    lD_day, lN_day = [], []
    for j in range(DAYS):
        lD_day.append(int(np.sum(schedule[:, j] == 1)))
        lN_day.append(int(np.sum(schedule[:, j] == 2)))

    # ✅ 結果をstateに保存
    app.state.jobs[job_id]["result"] = {
        "result": dic,
        "num_of_day": lD,
        "num_of_night": lN,
        "num_of_day_shift": lD_day,
        "num_of_night_shift": lN_day,
    }


# -------------------------------------------------------
# pulpによるシフト生成（既存エンドポイント、変更なし）
# -------------------------------------------------------

@app.post("/posts")
async def hello(firstday: int = Form()):
    M = list(range(1, 11))
    D = list(range(1, 32))
    C = ['/', 'D', 'N']
    Q = ['ND', 'NN', 'N/N']

    firstDay = firstday
    problem = pulp.LpProblem(sense=pulp.LpMinimize)
    x = pulp.LpVariable.dicts('x', [(m, d, c) for m in M for d in D for c in C], cat='Binary')

    for m in M:
        for d in D:
            problem += pulp.lpSum([x[m, d, c] for c in C]) == 1

    for d in D:
        weekday = (firstDay + (d - 1)) % 7
        is_weekend = (weekday == 0 or weekday == 6)
        if is_weekend:
            problem += pulp.lpSum([x[m, d, 'D'] for m in M]) == 2
            problem += pulp.lpSum([x[m, d, 'N'] for m in M]) == 1
        else:
            problem += pulp.lpSum([x[m, d, 'D'] for m in M]) == 6
            problem += pulp.lpSum([x[m, d, 'N'] for m in M]) == 1

    for m in M:
        problem += pulp.lpSum([x[m, d, C[1]] for d in D]) + pulp.lpSum([x[m, d, C[2]] for d in D]) <= 20
    for m in M:
        problem += pulp.lpSum([x[m, d, C[2]] for d in D]) <= 5

    for q in Q:
        t = len(q) - 1
        for m in M:
            for d in D[t:]:
                problem += pulp.lpSum([x[m, d - t + h, q[h]] for h in range(t + 1)]) <= t

    pulp.LpStatus[problem.solve()]

    dic = {}
    for p in M:
        buf = []
        for d in D:
            for c in C:
                if x[p, d, c].value():
                    buf.append(c)
        dic.setdefault(f'ナース{p}', buf)

    day_count_list = [sum(1 for d in D if dic[f"ナース{p}"][d - 1] != "/") for p in M]
    day_shift_list = [sum(1 for p in M if dic[f"ナース{p}"][d - 1] == "D") for d in D]
    night_shift_list = [sum(1 for p in M if dic[f"ナース{p}"][d - 1] == "N") for d in D]

    return {
        "result": dic,
        "num_of_day": day_count_list,
        "num_of_day_shift": day_shift_list,
        "num_of_night_shift": night_shift_list,
    }


# 以下はチーム内で協力してjupyter notebook上で作ったpulpのコードです。これをFastAPI上で動かすために、上記のようにコードを変更しました。
# @app.get("/")
# async def hello():

    # * リスト
    # M: ナースの集合
    M = list(range(1, 11))
    # D: 日付の集合
    D = list(range(1, 32))
    # C: 勤務区分の集合
    C = ['/', 'D', 'N'] # C[0]: 休み C[1]: 日勤 C[2]: 夜勤
    # Q: 禁止シフト1
    Q = ['ND','NN','N/N']
    day=['sunday','saturday','friday','thursday','wednesday','tuesday','monday','Sunday','Saturday','Friday','Thursday','Wednesday','Tuesday','Monday'
        ,'日曜日','土曜日','金曜日','木曜日','水曜日','火曜日','月曜日']
    firstDay=0
    # try:
    #     firstDay=day.index(input())%7
    # except ValueError: print("入力された曜日はリストにありません。正しい曜日を入力してください。")
    problem = pulp.LpProblem(sense=pulp.LpMinimize)
    # 変数
    # x[i, j, k]: ナース番号iがj日の勤務kであるかどうか
    x = pulp.LpVariable.dicts('x', [(m, d, c) for m in M for d in D for c in C], cat='Binary')
    #m*d*cのデータ量を持つ辞書X （1~10,1~30,N,D,/）の値が保存されている
    # その日の勤務は休み、昼勤、夜勤のどれか1つ
    for m in M:
        for d in D:
            problem += pulp.lpSum([x[m, d, c] for c in C]) == 1
    # 制約(0)
    # 平日は、6人のナースが日勤、１人が夜勤しなければならない
    #土日は２人のナースが日勤、１人が夜勤しなければならない
    for d in D:
        if (d%7!=firstDay and (d-1)%7!=firstDay):
        #if (d%7!=0 and d%7!=6):
            for q in Q:
                for c in C[1]:
                    problem += pulp.lpSum([x[m, d,C[1]] for m in M]) == 6
                for c in C[2]:
                    problem += pulp.lpSum([x[m, d,C[2]] for m in M]) == 1
        else:
            for q in Q:
                for c in C[1]:
                    problem += pulp.lpSum([x[m, d,C[1]] for m in M]) == 2
                for c in C[2]:
                    problem += pulp.lpSum([x[m, d,C[2]] for m in M]) == 1
    # 制約(1)
    # 勤務は20回以内にする
    for m in M:
        problem += pulp.lpSum([x[m, d, C[1]] for d in D])+ pulp.lpSum([x[m, d, C[2]] for d in D]) <= 20
    # 制約(2)
    # 夜勤をn回以内にする
    for m in M:
        problem += pulp.lpSum([x[m, d, C[2]] for d in D]) <= 5
    # 制約(4)
    # 夜勤の翌日の日勤は許されない
    #q0 = Q[0]
    #t = len(q0) - 1
    #for m in M:
    #    for d in D[t:]:
    #        problem += pulp.lpSum([x[m, d - t + h, q0[h]] for h in range(t+1)]) <= t
    for q in Q:
        t = len(q) - 1
        for m in M:
            for d in D[t:]:
                problem += pulp.lpSum([x[m, d - t + h, q[h]] for h in range(t+1)]) <= t
    pulp.LpStatus[problem.solve()]
    print('0, 1, 2, 3, 4, 5, 6, 7, 8, 9,10,11,12,13,14,15,16,17,18,19,20,21,22,23,24,25,26,27,28,29,30,31,/, D, N')
    for p in M:
        buf = []
        for d in D:
            for c in C:
                if x[p, d, c].value():
                    buf.append(f' {c}')
        print(f"{p},{','.join(buf)},{buf.count(' /'):2d},{buf.count(' D'):2d},{buf.count(' N'):2d}")
    for c in C[1:]:
        buf = []
        for d in D:
            buf.append(f" {str(int(sum([x[p, d, c].value() for p in M])))}")
        print(f"{c}:{','.join(buf)}")

    dic = {}
    for p in M:
        buf = []    
        for d in D:
            for c in C:
                if x[p, d, c].value():
                    buf.append(f' {c}')
            dic.setdefault(f'ナース{p}', buf)
    return dic

