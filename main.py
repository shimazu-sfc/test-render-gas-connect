import operator
from typing import Any, Dict, List, Optional, Union
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="Citrus Thinning Rule Engine (Fully Synced)")

# 基本比較演算子のマッピング
OPERATORS = {
    "==": operator.eq,
    "!=": operator.ne,
    "<": operator.lt,
    "<=": operator.le,
    ">": operator.gt,
    ">=": operator.ge,
}

# --- スキーマ定義 ---
class RuleCondition(BaseModel):
    logic: str = "AND"  # "AND" または "OR"
    field: str
    op: str
    value: Any

class ARDisplay(BaseModel):
    color: str
    label: str

class ThinningRule(BaseModel):
    id: str
    name: str
    applies_to: str = "Fruit"
    priority: int = 0
    action: str
    ar_display: ARDisplay
    conditions: List[RuleCondition] = []

class FruitSample(BaseModel):
    sample_id: str
    data: Dict[str, Any]

class EvaluationRequest(BaseModel):
    rules: List[ThinningRule]
    items: List[FruitSample]

class EvaluationResult(BaseModel):
    sample_id: str
    action: str
    rule_id: Optional[str] = None
    rule_name: Optional[str] = None
    ar_color: Optional[str] = None
    ar_label: Optional[str] = None
    matched_conditions: List[str] = []

# --- 演算評価ヘルパー ---
def evaluate_condition_op(actual_val: Any, op_str: str, target_val: Any) -> bool:
    if op_str.upper() == "BETWEEN":
        # "0.8-1.2" などの範囲文字列またはリストをパース
        try:
            if isinstance(target_val, str) and "-" in target_val:
                min_v, max_v = map(float, target_val.split("-"))
            elif isinstance(target_val, (list, tuple)) and len(target_val) == 2:
                min_v, max_v = float(target_val[0]), float(target_val[1])
            else:
                return False
            return min_v <= float(actual_val) <= max_v
        except (ValueError, TypeError):
            return False

    op_func = OPERATORS.get(op_str)
    if not op_func:
        return False

    try:
        # 文字列比較や型合わせ
        if isinstance(actual_val, str) and isinstance(target_val, str):
            return op_func(actual_val.strip().upper(), target_val.strip().upper())
        return bool(op_func(actual_val, target_val))
    except (TypeError, ValueError):
        return False

# --- 推論ロジック ---
def evaluate_single_sample(data: Dict[str, Any], rules: List[ThinningRule]) -> Dict[str, Any]:
    # priority が大きい順（降順）に評価
    sorted_rules = sorted(rules, key=lambda r: r.priority, reverse=True)

    for rule in sorted_rules:
        if not rule.conditions:
            continue

        matched_conditions = []
        overall_result = None

        for cond in rule.conditions:
            field = cond.field
            op_str = cond.op
            target_val = cond.value
            logic = cond.logic.upper()

            # 属性欠損ガード
            if field not in data or data[field] is None:
                current_match = False
            else:
                actual_val = data[field]
                current_match = evaluate_condition_op(actual_val, op_str, target_val)

            if current_match:
                matched_conditions.append(f"{field} {op_str} {target_val}")

            # 論理結合
            if overall_result is None:
                overall_result = current_match
            else:
                if logic == "OR":
                    overall_result = overall_result or current_match
                else:  # AND
                    overall_result = overall_result and current_match

        # ルール合致判定
        if overall_result and len(matched_conditions) > 0:
            return {
                "action": rule.action,
                "rule_id": rule.id,
                "rule_name": rule.name,
                "ar_color": rule.ar_display.color,
                "ar_label": rule.ar_display.label,
                "matched_conditions": matched_conditions
            }

    # デフォルト残果（フォールバック）
    return {
        "action": "KEEP",
        "rule_id": None,
        "rule_name": "摘果ルール非該当（健全果・観察継続）",
        "ar_color": "GREEN",
        "ar_label": "維持（標準）",
        "matched_conditions": []
    }

# --- エンドポイント ---
@app.get("/")
def root():
    return {"message": "Citrus Thinning Engine is ready."}

@app.post("/evaluate", response_model=List[EvaluationResult])
def evaluate_fruits(request: EvaluationRequest):
    results = []
    for item in request.items:
        res = evaluate_single_sample(item.data, request.rules)
        results.append(
            EvaluationResult(
                sample_id=item.sample_id,
                action=res["action"],
                rule_id=res["rule_id"],
                rule_name=res["rule_name"],
                ar_color=res["ar_color"],
                ar_label=res["ar_label"],
                matched_conditions=res["matched_conditions"]
            )
        )
    return results
