from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
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
    # return {"message" : "Hello,World"}

    # パラメータ
    # ナース
    M = list(range(1,9))
    # 日付
    D = list(range(1,15))
    # 勤務区分
    C = ['/', 'D', 'N']
    # 禁止シフト
    Q = ['ND', '/D/', '/N/']
    Q2 = ['DDDD/D', 'DDDD/N', 'DDDN/D', 'DDDN/N', 'DDNN/D', 'DDNN/N', 'DNNN/D', 'DNNN/N', 'NNNN/D', 'NNNN/N']

    problem = pulp.LpProblem(sense=pulp.LpMaximize)

    # 変数:x, key: (m,d,c), value: pulpの変数をとる
    x = pulp.LpVariable.dicts('x', [(m, d, c) for m in M for d in D for c in C], cat='Binary')
    y = pulp.LpVariable.dicts('y', [(m, i) for m in M for i in [0, 1]], cat='Binary')

    # その日の勤務は休み、昼勤、夜勤のどれか1つ???
    for m in M:
        for d in D:
            problem += pulp.lpSum([x[m,d,c] for c in C]) == 1

    # 制約0
    for d in D:
        for c in C[1:]:
            problem += pulp.lpSum([x[m,d,c] for m in M]) == 2

    # 制約1
    for m in M:
        problem += pulp.lpSum([x[m, d, C[0]] for d in D]) >= 7

    #制約2
    for m in M:
        problem += pulp.lpSum([y[m, i] for i in [0, 1]]) >= 1
        problem += x[m, 6, C[0]] + x[m, 7, C[0]] == y[m, 0] * 2
        problem += x[m, 13, C[0]] + x[m, 14, C[0]] == y[m, 1] * 2

    #制約3
    for m in M:
        for d in D[4:]:        
            problem += pulp.lpSum([x[m, d - h, c] for h in range(4 + 1) for c in C[1:]]) <= 4

    # 制約(4)
    # 夜勤の翌日の日勤は許されない
    q0 = Q[0]
    t = len(q0) - 1
    for m in M:
        for d in D[t:]:
            problem += pulp.lpSum([x[m, d - t + h, q0[h]] for h in range(t+1)]) <= t
    # 制約(5)
    # 夜勤は3日連続までしか許されない
    for m in M:
        for d in D[3:]:        
            problem += pulp.lpSum([x[m, d - h, C[2]] for h in range(3 + 1)]) <= 3

    # ----- 条件6からは可能であればの条件。
    # 制約(6)
    # 前後が休みになる孤立勤務を避ける
    for m in M:
        for q in Q[1:]:
            t = len(q) - 1
            for d in D[t:]:
                problem += pulp.lpSum([x[m, d - t + h, q[h]] for h in range(t+1)]) <= t
    # 制約(7)
    # 4連続勤務を避ける。避けられない場合は直後の2日間を休みにする
    # * 4連続勤務の場合、増える何かを作って最小化すれば良いと思う...
    for m in M:
        for q in Q2:
            t = len(q) - 1
            for d in D[t:]:
                problem += pulp.lpSum([x[m, d - t + h, q[h]] for h in range(t+1)]) <= t

    pulp.LpStatus[problem.solve(pulp.PULP_CBC_CMD(msg = False))]

    # print(' , 1, 2, 3, 4, 5, 6, 7, 8, 9,10,11,12,13,14')
    dic = {}
    for p in M:
        buf = []    
        for d in D:
            for c in C:
                if x[p, d, c].value():
                    buf.append(f' {c}')
            dic.setdefault(f'ナース{p}', buf)
    return dic