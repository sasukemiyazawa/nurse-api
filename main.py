from fastapi import FastAPI, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel
import pulp

app = FastAPI()

origins = [
    "http://localhost:3000"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers={"*"},
)


@app.get("/")
async def hello():

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


# class Item(BaseModel):
#     num: str


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
    return dic