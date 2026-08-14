from typing import Any, Dict, List, Optional
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(title="Citrus Thinning Rule Engine")

# --- リクエスト・レスポンスの型定義 ---
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

# --- 推論エンドポイント ---
@app.post("/evaluate", response_model=List[EvaluationResult])
def evaluate_fruits(request: EvaluationRequest):
    results = []
    
    for item in request.items:
        # DSLルールエンジンによる推論を実行（既存の評価ロジックを呼び出し）
        # 例: res = engine.evaluate(item.data)
        eval_result = run_dsl_engine(item.data)
        
        results.append(
            EvaluationResult(
                sample_id=item.sample_id,
                action=eval_result.get("action", "KEEP"),
                rule_id=eval_result.get("rule_id"),
                reason=eval_result.get("reason", "ルール適用結果"),
                matched_conditions=eval_result.get("matched_conditions", [])
            )
        )
        
    return results

def run_dsl_engine(fruit_data: Dict[str, Any]) -> Dict[str, Any]:
    # 既存のDSLエンジン呼び出しコード
    # ...
    return {
        "action": "THIN_OUT",
        "rule_id": "RULE_001",
        "reason": "小玉基準に該当",
        "matched_conditions": ["diameter_mm < 25.0"]
    }
