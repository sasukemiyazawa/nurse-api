# ナーススケジューリングアプリ

本アプリは、授業の一環として開発した **ナースのシフト自動作成アプリ**です。  
バックエンドでは数理最適化または遺伝的アルゴリズムを用いてシフト案を自動生成し、  
フロントエンドでは MUI を用いた UI により、ブラウザから直感的に操作できます。

---

# プロダクト構成

## バックエンド（Python: 数理最適化 / GA）
- ナースの希望・制約を入力として受け取り、最適なシフトを自動生成
- 数理最適化（最大化 / 最小化問題）または GA（遺伝的アルゴリズム）で解を探索
- REST API としてフロントエンドに結果を返却

  https://github.com/sasukemiyazawa/nurse-api

## フロントエンド（React + MUI）
- ブラウザから直接 API を叩かずに操作できる UI
- シフト表を MUI のテーブルで視覚的に表示
- パラメータ入力 → 最適化実行 → 結果表示までをワンストップで提供
<img width="1099" height="477" alt="スクリーンショット 2026-03-23 16 34 28" src="https://github.com/user-attachments/assets/d06c3d4d-f263-4baf-bebc-ea4565bb4869" />
<img width="769" height="511" alt="スクリーンショット 2026-03-23 16 36 25" src="https://github.com/user-attachments/assets/958174fd-ce47-4a25-aa96-3b5bc62c17db" />


---

# 数理モデル

本アプリでは、ナースのシフト割り当てを以下のような最適化問題として定式化しています。

## 変数
ナース $\( i \)$、日付 $\( d \)$、シフト種別$\( s \)$ に対して：

$`
x_{i,d,s} =
\begin{cases} 
1 & \text{ナース } i \text{ が} d \text{日の }\text{ にシフト } s \text{ に入る場合} \\
0 & \text{それ以外}
\end{cases}
`$


## 目的関数（例：希望を最大化）
$`
\max \sum_{i,d,s} w_{i,d,s} \cdot x_{i,d,s}
`$

$\( w_{i,d,s} \)：希望度（希望シフトなら 1、嫌なシフトなら -1 など）$

## 制約条件（Constraints）

### 1. 1 日に 1 つの勤務区分のみ
$$
\sum_{c \in \{/,D,N\}} x_{i,d,c} = 1
$$

---

### 2. 必要人数制約（平日 / 休日）

#### 平日（weekday ≠ 0,6）
$$
\sum_i x_{i,d,D} = 6
$$

$$
\sum_i x_{i,d,N} = 1
$$

#### 土日（weekday = 0 \text{ or } 6）
$$
\sum_i x_{i,d,D} = 2
$$

$$
\sum_i x_{i,d,N} = 1
$$

---

### 3. 勤務回数の上限

#### 総勤務回数（D + N）は 20 回以内
$$
\sum_d x_{i,d,D} + \sum_d x_{i,d,N} \le 20
$$

#### 夜勤は 5 回以内
$$
\sum_d x_{i,d,N} \le 5
$$

---

### 4. 禁止シフト（連続勤務の禁止）

禁止パターン：  
- ND（夜勤 → 日勤）  
- NN（夜勤 → 夜勤）  
- N/N（夜勤 → 休み → 夜勤）

一般形：
$$
\sum_{h=0}^{t} x_{i, d - t + h, q_h} \le t
$$

代表例（ND）：
$$
x_{i,d,N} + x_{i,d+1,D} \le 1
$$

---

### 5. 変数定義
$$
x_{i,d,c} =
\begin{cases}
1 & \text{ナース } i \text{ が日 } d \text{ に勤務 } c \text{ の場合} \\
0 & \text{それ以外}
\end{cases}
$$


---

# Setup（環境構築）

本アプリは **FastAPI（バックエンド）** と **React + MUI（フロントエンド）** の 2 つで構成されています。

---

## Backend（FastAPI）

### 依存パッケージのインストール

```

pip install -r requirements.txt


```

### 起動
```

uvicorn main:app --reload

```
起動後、API は以下でアクセスできます：

• http://localhost:8000/ga/start

• http://localhost:8000/ga/status/{job_id}

• http://localhost:8000/ga/result/{job_id}

• http://localhost:8000/posts （PuLP 版）
