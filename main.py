from fastapi import FastAPI
from pydantic import BaseModel
import datetime

app = FastAPI()

# GASから送られてくるデータの型定義
class TestRequest(BaseModel):
    message: str
    fruit_id: str

# 動作確認用のルート
@app.get("/")
def read_root():
    return {"status": "Render Python API is running!"}

# GASから呼び出すテスト用API
@app.post("/test_evaluate")
def evaluate(data: TestRequest):
    received_msg = data.message
    target_id = data.fruit_id
    
    output_text = f"【Python判定結果】{target_id} に対して '{received_msg}' を受け取りました。ルールR01を適用し『摘果(THIN)』と判定しました。"
    
    return {
        "status": "success",
        "timestamp": datetime.datetime.now().isoformat(),
        "evaluated_text": output_text,
        "action": "THIN",
        "rule_id": "R01_cluster_top_small"
    }
