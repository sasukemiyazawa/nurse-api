# 起動コマンド uvicorn main:app --reload

from fastapi import FastAPI, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel
import pulp

from typing import List

from fastapi import BackgroundTasks, FastAPI
from fastapi_mail import ConnectionConfig, FastMail, MessageSchema, MessageType
from pydantic import BaseModel, EmailStr
from starlette.responses import JSONResponse

import os


app = FastAPI()

origins = [
    "http://localhost:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers={"*"},
)

# pulpによるシフト生成
@app.post("/posts")
async def hello(firstday: int = Form()):

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
    firstDay=firstday
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
    print(dic)
    return dic

# tokenの取得
@app.get("/token")
async def get_credential():
    """
    アクセストークンの取得

    カレントディレクトリに pickle 形式でトークンを保存し、再利用できるようにする。（雑ですみません。。）
    """
    from google_auth_oauthlib.flow import InstalledAppFlow

    SCOPES = ['https://mail.google.com/']

    flow = InstalledAppFlow.from_client_secrets_file(
    './client_secret.json', SCOPES)
    creds = flow.run_local_server(port=0)

    with open('token.json', 'w') as token:
        token.write(creds.to_json()) 
    return ("complete")
    
# メール関係のプログラム
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from email.mime.text import MIMEText
import base64

def message_base64_encode(message):
    return base64.urlsafe_b64encode(message.as_bytes()).decode()


def mail_post(mail_text, mail_to, title):
    scopes = ['https://mail.google.com/']
    creds = Credentials.from_authorized_user_file('token.json', scopes)
    service = build('gmail', 'v1', credentials=creds)

    message = MIMEText(f'{mail_text}')
    message['To'] = f'{mail_to}'
    message['From'] = 'sasuke.miyazawa@gmail.com'
    message['Subject'] = f'{title}'

    raw = {'raw': message_base64_encode(message)}
    service.users().messages().send(
        userId='me',
        body=raw
    ).execute()

async def mail():
    mail_text = "http://localhost:3000/ga/result"
    mailaddress = "b1020251@fun.ac.jp"#送信先のメールアドレス
    mail_title = "メールのタイトル"
    mail_post(mail_text, mailaddress, mail_title)


async def function():
    await ga()
    await mail()
    print(app.state.result)


# gaによるシフト生成

import random
from deap import base, creator, tools, algorithms
import numpy as np
import time
import json

@app.get("/ga")
async def res(background_tasks: BackgroundTasks):
    background_tasks.add_task(function)
    # background_tasks.add_task(mail)
    return "hello"

@app.get("/ga/result")
async def result():
    dic = app.state.result
    # buff = dic.item()
    # print(buff)
    return dic

async def ga():
    #hof削除ver
    # ナースの人数とスケジュール期間
    NUM_NURSES = 10
    DAYS = 30
    MAX_WORKING_DAYS = 20
    # 適応度クラスの作成
    creator.create("FitnessMin", base.Fitness, weights=(-1.0,))
    # 個体クラスの作成
    creator.create("Individual", np.ndarray, fitness=creator.FitnessMin)
    # Toolboxの作成
    toolbox = base.Toolbox()
    # 遺伝子を生成する関数"attr_gene"を登録 ok
    toolbox.register("attr_gene", random.randint, 0, 2)
    # 個体を生成する関数”individual"を登録
    toolbox.register("individual", tools.initRepeat, creator.Individual,
                    toolbox.attr_gene, NUM_NURSES * DAYS)
    # 個体集団を生成する関数"population"を登録
    toolbox.register("population", tools.initRepeat, list, toolbox.individual)
    def evaluate(individual):
        individual = np.array(individual).reshape(NUM_NURSES, DAYS)
        penalty = 0
        # 制約条件の評価
        for nurse in range(NUM_NURSES):
            working_days = np.sum(individual[nurse] > 0)
            if working_days > MAX_WORKING_DAYS:
                penalty += (working_days - MAX_WORKING_DAYS) * 10
            for day in range(DAYS):
                if individual[nurse][day] == 2 and day + 1 < DAYS:
                    if individual[nurse][day + 1] != 0:
                        penalty += 10
        # シフト要件の評価
        for day in range(DAYS):
            if day % 7 < 5:  # 平日
                day_shift = np.sum(individual[:, day] == 1)
                night_shift = np.sum(individual[:, day] == 2)
                if day_shift != 6:
                    penalty += abs(day_shift - 6) * 10
                if night_shift != 2:
                    penalty += abs(night_shift - 2) * 10
            else:  # 休日
                day_shift = np.sum(individual[:, day] == 1)
                night_shift = np.sum(individual[:, day] == 2)
                if day_shift != 2:
                    penalty += abs(day_shift - 2) * 10
                if night_shift != 1:
                    penalty += abs(night_shift - 1) * 10
        return penalty,
    # 評価関数"evaluate"を登録
    toolbox.register("evaluate", evaluate)
    # 交叉を行う関数"mate"を登録　２点交叉，１点交叉を混ぜて交叉する
    toolbox.register("mate", tools.cxUniform, indpb=0.5)
    # 変異を行う関数"mutate"を登録lowが最小の値
    toolbox.register("mutate", tools.mutUniformInt, low=0, up=2, indpb=0.2)
    # 個体選択法"select"を登録　トーナメントサイズを2
    toolbox.register("select", tools.selTournament, tournsize=2)

    random.seed(int(time.time()))
    # GAパラメータ
    N_GEN = 10
    POP_SIZE = 5000
    CX_PB = 0.9
    MUT_PB = 0.1
    # 個体集団の生成
    pop = toolbox.population(n=POP_SIZE)
    print("Start of evolution")
    # 統計情報を収集するためのオブジェクト アルゴリズムには直接関係ない
    stats = tools.Statistics(lambda ind: ind.fitness.values)
    stats.register("avg", np.mean)
    stats.register("std", np.std)
    stats.register("min", np.min)
    stats.register("max", np.max)
    """
    # ホールオブフェームを使用して最良個体を追跡
    hof = tools.HallOfFame(1,np.array_equal)
    """
    # アルゴリズムの実行
    algorithms.eaSimple(pop, toolbox, cxpb=CX_PB, mutpb=MUT_PB, ngen=N_GEN,
                        stats=stats, halloffame=None, verbose=True)
    print("-- End of (successful) evolution --")
    # 最良個体の抽出
    best_ind = tools.selBest(pop, 1)[0]
    print("Best individual is %s, %s" % (best_ind, best_ind.fitness.values))
    print("Schedule:\n", np.array(best_ind).reshape(NUM_NURSES, DAYS))

    dic = {}
    for i in range(10):
        buff=[]
        for j in range(30):
            buff.append(np.array(best_ind).reshape(NUM_NURSES, DAYS)[i][j].item())
        dic.setdefault(f'ナース{i+1}', buff)
    app.state.result = dic

    print(dic)
    return 0




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

