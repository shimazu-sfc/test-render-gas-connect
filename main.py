from fastapi import FastAPI
import yaml
import datetime

app = FastAPI()

# ---------------------------------------------------------
# 1. DSLルール (YAML形式で直接定義)
# ---------------------------------------------------------
RULES_YAML_TEXT = """
rules:
  - rule_id: R01_cluster_top_small
    name: "果房内の上部・小果の摘果"
    priority: 80
    applies_to: Fruit
    when:
      AND:
        - is_cluster_member: true
        - cluster_size: { operator: ">=", value: 3 }
        - position_in_cluster: "TOP"
        - ratio_to_cluster_mean_area: { operator: "<", value: 0.85 }
    then:
      action: THIN
      ar_display: { color: "RED", label: "摘果（上部・小果）" }

  - rule_id: R02_direct_flower_fruit
    name: "無葉花果（直花果）の摘果"
    priority: 90
    applies_to: Fruit
    when:
      AND:
        - is_direct_flower: true
    then:
      action: THIN
      ar_display: { color: "RED", label: "摘果（直花果）" }

  - rule_id: R03_july_outlier_huge
    name: "飛び抜け大玉（す上がり予兆果）の摘果"
    priority: 95
    applies_to: Fruit
    when:
      AND:
        - ratio_to_tree_mean_area: { operator: ">", value: 1.5 }
    then:
      action: THIN
      ar_display: { color: "RED", label: "摘果（極重大玉・す上がりリスク）" }

  - rule_id: R04_july_outlier_tiny
    name: "極小果の早期摘果"
    priority: 85
    applies_to: Fruit
    when:
      AND:
        - ratio_to_tree_mean_area: { operator: "<", value: 0.6 }
    then:
      action: THIN
      ar_display: { color: "RED", label: "摘果（極小果）" }

  - rule_id: R05_upward_fruit
    name: "立ち枝・上向き果の日焼け防止摘果"
    priority: 90
    applies_to: Fruit
    when:
      AND:
        - is_top_side: true
        - orientation_angle: { operator: ">", value: 45 }
    then:
      action: THIN
      ar_display: { color: "RED", label: "摘果（上向き果）" }

  - rule_id: R06_elongated_fruit
    name: "縦長異形果の摘果"
    priority: 75
    applies_to: Fruit
    when:
      AND:
        - aspect_ratio: { operator: ">", value: 1.1 }
    then:
      action: THIN
      ar_display: { color: "RED", label: "摘果（縦長果）" }

  - rule_id: R07_defected_fruit
    name: "傷果・病害虫被害果の最優先摘果"
    priority: 100
    applies_to: Fruit
    when:
      OR:
        - has_wind_scar: true
        - has_disease_spot: true
        - has_pest_damage: true
    then:
      action: THIN
      ar_display: { color: "RED", label: "摘果（障害果）" }

  - rule_id: R08_bottom_skirt_fruit
    name: "裾枝果実の泥跳ね・腐敗防止摘果"
    priority: 85
    applies_to: Fruit
    when:
      AND:
        - ground_clearance: { operator: "<", value: 50 }
    then:
      action: THIN
      ar_display: { color: "RED", label: "摘果（裾枝果）" }

  - rule_id: R09_ideal_downward_fruit
    name: "下垂有葉果の優先保護"
    priority: 95
    applies_to: Fruit
    when:
      AND:
        - is_bottom_side: true
        - is_leaf_associated: true
        - aspect_ratio: { operator: "<", value: 0.85 }
        - ratio_to_tree_mean_area: { operator: "BETWEEN", min: 0.8, max: 1.2 }
    then:
      action: KEEP
      ar_display: { color: "GREEN", label: "保護（優良果）" }
"""

# ---------------------------------------------------------
# 2. 評価エンジンロジック（型ガード安全版）
# ---------------------------------------------------------
def evaluate_condition(feature_val, condition):
    # 値が存在しない (None) 場合は判定スキップ
    if feature_val is None:
        return False
        
    if isinstance(condition, dict):
        op = condition.get('operator')
        val = condition.get('value')
        
        # 比較対象のデータ型が合わない場合のエラー回避ガード
        try:
            if op == '>': return feature_val > val
            if op == '>=': return feature_val >= val
            if op == '<': return feature_val < val
            if op == '<=': return feature_val <= val
            if op == '==': return feature_val == val
            if op == 'BETWEEN':
                return condition['min'] <= feature_val <= condition['max']
        except TypeError:
            return False
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
    # 優先度 (priority) の高い順にソート
    sorted_rules = sorted(rules, key=lambda x: x.get('priority', 0), reverse=True)

    results = []

    for obj in detected_fruits:
        matched_rule = None
        
        # 優先度の高いルールから順に評価し、最初にヒットしたものを採用 (コンフリクト解決)
        for rule in sorted_rules:
            if rule.get('applies_to') == 'Fruit':
                if evaluate_rule_when(obj, rule['when']):
                    matched_rule = rule
                    break

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
            # どのルールにも合致しない場合のデフォルト動作
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
# 3. エンドポイント設定
# ---------------------------------------------------------
@app.get("/")
def read_root():
    return {"status": "Render Python API is running!"}

@app.post("/evaluate_dsl_test")
def evaluate_dsl_endpoint():
    # 内蔵のYAMLテキストをロード
    dsl_rules = yaml.safe_load(RULES_YAML_TEXT)

    # 単体テスト用サンプルデータ (3つの異なる条件を持つ果実)
    sample_detected_fruits = [
        {
            "fruit_id": "fruit_01",
            "is_cluster_member": True,
            "cluster_size": 3,
            "position_in_cluster": "TOP",
            "ratio_to_cluster_mean_area": 0.70,
            "ratio_to_tree_mean_area": 0.9,
            "is_direct_flower": False,
            "has_wind_scar": False
        },
        {
            "fruit_id": "fruit_02",
            "is_cluster_member": False,
            "ratio_to_tree_mean_area": 1.8, # 飛び抜け大玉 (Priority 95)
            "is_direct_flower": False,
            "has_wind_scar": True  # 傷あり (Priority 100 ➔ こちらが勝つ)
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

    # DSLエンジンの実行
    evaluation_results = run_dsl_engine(sample_detected_fruits, dsl_rules)

    return {
        "status": "success",
        "timestamp": datetime.datetime.now().isoformat(),
        "evaluated_count": len(evaluation_results),
        "results": evaluation_results
    }
