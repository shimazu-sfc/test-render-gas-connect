import operator
from typing import Any, Dict, List, Optional
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="Citrus Thinning Rule Engine")

# ==============================================================================
# 1. 青島温州（7月粗摘果・表年）ルール定義
# priority: 数値が小さいほど優先度が高い（競合解決用）
# ==============================================================================
RULES = [
    {
        "id": "RULE_001",
        "priority": 1,
        "action": "THIN_OUT",
        "reason": "病害虫被害果の摘除",
        "conditions": [
            {"field": "has_pest_damage", "op": "==", "value": True}
        ]
    },
    {
        "id": "RULE_002",
        "priority": 2,
        "action": "THIN_OUT",
        "reason": "著しい傷果・奇形果の摘除",
        "conditions": [
            {"field": "has_scar", "op": "==", "value": True}
        ]
    },
    {
        "id": "RULE_003",
        "priority": 3,
        "action": "THIN_OUT",
        "reason": "粗摘果基準：小玉果（横径25mm未満）の摘除",
        "conditions": [
            {"field": "diameter_mm", "op": "<", "value": 25.0}
        ]
    },
    {
        "id": "RULE_004",
        "priority": 4,
        "action": "THIN_OUT",
        "reason": "葉果比不足（20未満）による摘除",
        "conditions": [
            {"field": "leaf_fruit_ratio", "op": "<", "value": 20.0}
        ]
    },
    {
        "id": "RULE_005",
        "priority": 10,
        "action": "KEEP",
        "reason": "健全果（適正サイズ・日当たり良好）のため育成継続",
        "conditions": [
            {"field": "diameter_mm", "op": ">=", "value": 25.0},
            {"field": "has_pest_damage", "op": "==", "value": False},
            {"field": "sunlit", "op": "==", "value": True}
        ]
    }
]

# 比較演算子のマッピング
OPERATORS = {
    "==": operator.eq,
    "!=": operator.ne,
    "<": operator.lt,
    "<=": operator.le,
    ">": operator.gt,
    ">=": operator.ge,
}

# ==============================================================================
# 2. DSL評価・推論エンジン
# ==============================================================================
def evaluate_sample(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    1つの果実データに対してルール群を評価し、優先度順に適用する
    """
    # 優先度順（昇順）にソート
    sorted_rules = sorted(RULES, key=lambda r: r.get("priority", 999))

    for rule in sorted_rules:
        matched_conditions = []
        is_all_matched = True

        for cond in rule.get("conditions", []):
            field = cond["field"]
            op_str = cond["op"]
            target_val = cond["value"]

            # データ欠損時の安全ガード：必要な属性が存在しない場合はマッチ不成立
            if field not in data or data[field] is None:
                is_all_matched = False
                break

            actual_val = data[field]
            op_func = OPERATORS.get(op_str)

            if not op_func:
                is_all_matched = False
                break

            try:
                # 比較実行
                if op_func(actual_val, target_val):
                    matched_conditions.append(f"{field} {op_str} {target_val}")
                else:
                    is_all_matched = False
                    break
            except TypeError:
                # 型不一致などで比較失敗した場合は不一致扱い
                is_all_matched = False
                break

        # ルール内の全条件が成立した場合、そのルールを採用してリターン
        if is_all_matched and len(matched_conditions) > 0:
            return {
                "action": rule["action"],
                "rule_id": rule["id"],
                "reason": rule["reason"],
                "matched_conditions": matched_conditions
            }

    # どのルールにも明示的に合致しなかった場合のデフォルト（安全側：残果）
    return {
        "action": "KEEP",
        "rule_id": None,
        "reason": "摘果対象ルールに該当なし（デフォルト残果）",
        "matched_conditions": []
    }

# ==============================================================================
# 3. FastAPI リクエスト / レスポンス スキーマ & エンドポイント
# ==============================================================================
class FruitSample(BaseModel):
    sample_id: str
    data: Dict[str, Any]

class EvaluationRequest(BaseModel):
    items: List[FruitSample]

class EvaluationResult(BaseModel):
    sample_id: str
    action: str
    rule_id: Optional[str] = None
    reason: str
    matched_conditions: List[str] = []

@app.get("/")
def root():
    return {"message": "Citrus Thinning Rule Engine is running."}

@app.post("/evaluate", response_model=List[EvaluationResult])
def evaluate_fruits(request: EvaluationRequest):
    results = []
    
    for item in request.items:
        eval_result = evaluate_sample(item.data)
        
        results.append(
            EvaluationResult(
                sample_id=item.sample_id,
                action=eval_result["action"],
                rule_id=eval_result["rule_id"],
                reason=eval_result["reason"],
                matched_conditions=eval_result["matched_conditions"]
            )
        )
        
    return results
