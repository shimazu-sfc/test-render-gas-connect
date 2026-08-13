from fastapi import FastAPI
from pydantic import BaseModel
import yaml
import datetime
import os

app = FastAPI()

# ---------------------------------------------------------
# DSL評価ロジック
# ---------------------------------------------------------
def evaluate_condition(feature_val, condition):
    if isinstance(condition, dict):
        op = condition.get('operator')
        val = condition.get('value')
        
        if op == '>': return feature_val > val
        if op == '>=': return feature_val >= val
        if op == '<': return feature_val < val
        if op == '<=': return feature_val <= val
        if op == '==': return feature_val == val
        if op == 'BETWEEN':
            return condition['min'] <= feature_val <= condition['max']
    else:
        return feature_val == condition
    return False

def evaluate_rule_when(features, when_clause):
    if 'AND' in when_clause:
        for cond in when_clause['AND']:
            key = list(cond.keys())[0]
            val = cond[key]
            if not evaluate_condition(features.get(key), val):
                return False
        return True

    if 'OR' in when_clause:
        for cond in when_clause['OR']:
            key = list(cond.keys())[0]
            val = cond[key]
            if evaluate_condition(features.get(key), val):
                return True
        return False

    return False

def run_dsl_engine(detected_fruits, dsl_rules_yaml):
    rules = dsl_rules_yaml.get('rules', [])
    sorted_rules = sorted(rules, key=lambda x: x.get('priority', 0), reverse=True)

    results = []

    for obj in detected_fruits:
        matched_rule = None
        
        for rule in sorted_rules:
            if rule.get('applies_to') == 'Fruit':
                if evaluate_rule_when(obj, rule['when']):
                    matched_rule = rule
                    break  # 最高優先度のルールを採用 (Priority解決)

        if matched_rule:
            results.append({
                "fruit_id": obj.get("fruit_id"),
                "action": matched_rule['then']['action'],
                "rule_id": matched_rule['rule_id'],
                "rule_name": matched_rule['name'],
                "priority": matched_rule['priority'],
                "ar_display": matched_rule['then']['ar_display']
            })
        else:
            results.append({
                "fruit_id": obj.get("fruit_id"),
                "action": "KEEP",
                "rule_id": "DEFAULT_KEEP",
                "rule_name": "標準保護（合致ルールなし）",
                "priority": 0,
                "ar_display": {"color": "GREEN", "label": "保護"}
            })

    return results

# ---------------------------------------------------------
# エンドポイント
# ---------------------------------------------------------
@app.get("/")
def read_root():
    return {"status": "Render Python API is running!"}

@app.post("/evaluate_dsl_test")
def evaluate_dsl_endpoint():
    # 1. YAMLルールの読み込み
    yaml_path = os.path.join(os.path.dirname(__file__), "rules.yaml")
    with open(yaml_path, "r", encoding="utf-8") as f:
        dsl_rules = yaml.safe_load(f)

    # 2. テスト用サンプルデータ（異なる特徴を持つ3つの果実）
    sample_detected_fruits = [
        {
            "fruit_id": "fruit_01",
            "is_cluster_member": True,
            "cluster_size": 3,
            "position_in_cluster": "TOP",
            "ratio_to_cluster_mean_area": 0.70, # 小果 (0.85未満)
            "ratio_to_tree_mean_area": 0.9,
            "is_direct_flower": False,
            "has_wind_scar": False
        },
        {
            "fruit_id": "fruit_02",
            "is_cluster_member": False,
            "ratio_to_tree_mean_area": 1.8, # 飛び抜け大玉 (>1.5)
            "is_direct_flower": False,
            "has_wind_scar": True # 傷あり (Priority 100)
        },
        {
            "fruit_id": "fruit_03",
            "is_bottom_side": True,
            "is_leaf_associated": True,
            "aspect_ratio": 0.80, # 扁平果
            "ratio_to_tree_mean_area": 1.0,
            "is_direct_flower": False,
            "has_wind_scar": False
        }
    ]

    # 3. DSLエンジン実行
    evaluation_results = run_dsl_engine(sample_detected_fruits, dsl_rules)

    return {
        "status": "success",
        "timestamp": datetime.datetime.now().isoformat(),
        "evaluated_count": len(evaluation_results),
        "results": evaluation_results
    }
