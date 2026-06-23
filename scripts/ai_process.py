"""
AI智能加工脚本
调用 MiMo API 将原始数据转化为结构化备考内容
- 宏观数据 → 趋势解读 + 考点映射
- 热点论文 → 备考素材 + 考点关联
"""
import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path

import requests

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
ROOT_DIR = Path(__file__).resolve().parent.parent

MIMO_URL = "https://api.xiaomimimo.com/v1/chat/completions"
MIMO_MODEL = "mimo-v2.5"

def get_api_key():
    """获取 MiMo API Key，优先环境变量，其次从index.html提取"""
    key = os.environ.get("MIMO_API_KEY", "")
    if key:
        return key
    
    # 尝试从 index.html 的 getAPIKey() 函数中提取
    html_path = ROOT_DIR / "index.html"
    if html_path.exists():
        import re
        with open(html_path, "r") as f:
            html = f.read()
        m = re.search(r'function getAPIKey\(\)\{return\s*"([^"]+)"', html)
        if m:
            return m.group(1)
    
    return ""

HEADERS = None  # Will be set when key is available

def call_mimo(system_prompt, user_prompt, max_tokens=2000):
    """调用 MiMo API"""
    key = get_api_key()
    if not key:
        print("  [WARN] API Key 未找到，跳过 AI 加工")
        return None
    
    global HEADERS
    if HEADERS is None:
        HEADERS = {
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        }
    
    try:
        resp = requests.post(
            MIMO_URL,
            headers=HEADERS,
            json={
                "model": MIMO_MODEL,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "max_tokens": max_tokens,
                "temperature": 0.3,
            },
            timeout=60,
        )
        
        if resp.status_code != 200:
            print(f"  [ERROR] API 返回 {resp.status_code}: {resp.text[:200]}")
            return None
        
        data = resp.json()
        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        return content
    
    except Exception as e:
        print(f"  [ERROR] API 调用失败: {e}")
        return None


def extract_json(text):
    """从AI响应中提取JSON"""
    if not text:
        return None
    
    # 尝试直接解析
    try:
        return json.loads(text)
    except:
        pass
    
    # 尝试提取 ```json ... ``` 代码块
    m = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except:
            pass
    
    # 尝试提取 { ... } 对象
    m = re.search(r"\{[\s\S]*\}", text)
    if m:
        try:
            return json.loads(m.group(0))
        except:
            pass
    
    print(f"  [WARN] 无法解析 AI 响应为 JSON，原始: {text[:300]}")
    return None


def process_macro_data(item, related_knowledge_keys):
    """
    AI 加工宏观数据：趋势解读 + 考点映射
    item: 指标名称和最新数据
    related_knowledge_keys: 相关知识点key列表
    """
    system_prompt = """你是人大434国际商务考研辅导老师。
请根据给定的宏观经济指标数据，生成备考解读。
输出纯JSON格式（不要markdown代码块）:
{
  "trend": "趋势一句话（如：连续三个月上升）",
  "exam_angle": "在434考试中的可能考查角度（关联哪个理论，30字内）",
  "exam_question_type": "可能出现的题型（简答/论述/案例）",
  "related_knowledge": ["知识点key1", "知识点key2"]
}"""
    
    user_prompt = f"""指标名称: {item.get('name', '')}
最新数值: {item.get('latest_value', '')}
变化: {item.get('change', '')}
描述: {item.get('description', '')}

相关知识点: {', '.join(related_knowledge_keys[:5])}

请生成备考解读JSON。"""
    
    result = call_mimo(system_prompt, user_prompt, max_tokens=500)
    return extract_json(result)


def process_hotspot_item(item):
    """
    AI 加工热点论文：生成结构化备考素材
    """
    system_prompt = """你是人大434国际商务考研辅导老师。
请根据以下学术论文信息，生成结构化的备考热点素材。
输出纯JSON格式（不要markdown代码块）:
{
  "title": "精简标题（15字内）",
  "category": "所属434知识模块（从以下选：国际贸易理论/国际贸易政策/国际金融/跨国公司与国际化/中国对外经济/国际商务管理/新兴议题）",
  "summary": "核心观点（80字内，用考研学生能理解的语言）",
  "exam_relevance": "与434考试的具体关联（哪个理论、哪种题型可能考到，30字内）",
  "related_topics": ["关联知识点1", "关联知识点2"],
  "priority": "★★★ 或 ★★ 或 ★（根据与434考纲的关联度）"
}"""
    
    user_prompt = f"""论文标题: {item.get('title', '')}
作者（导师）: {item.get('professor', '')}
来源: {item.get('source', '')} {item.get('journal', '')}
年份: {item.get('year', '')}

请生成备考素材JSON。"""
    
    result = call_mimo(system_prompt, user_prompt, max_tokens=600)
    return extract_json(result)


def process_macro_data_batch():
    """批量加工宏观数据"""
    macro_path = DATA_DIR / "macro_data.json"
    if not macro_path.exists():
        print("[macro] macro_data.json 不存在，跳过")
        return None
    
    with open(macro_path, "r", encoding="utf-8") as f:
        macro = json.load(f)
    
    indicators = macro.get("dashboard", {}).get("indicators", [])
    if not indicators:
        print("[macro] 没有指标数据")
        return None
    
    # 知识模块映射
    knowledge_map = {
        "CFETS": ["汇率理论", "国际收支"],
        "美元": ["汇率理论", "国际收支", "蒙代尔-弗莱明模型"],
        "CPI": ["汇率理论", "国际收支"],
        "PPI": ["汇率理论"],
        "PMI": ["国际收支", "中国对外经济"],
        "M2": ["汇率理论", "蒙代尔-弗莱明模型"],
        "贸易差额": ["比较优势理论", "要素禀赋理论(H-O)", "中国对外经济"],
    }
    
    interpretations = {}
    for ind in indicators:
        name = ind.get("name", "")
        data = ind.get("data", [])
        if not data:
            continue
        
        latest = data[-1]
        prev = data[-2] if len(data) > 1 else latest
        
        latest_val = latest.get("value", "N/A")
        change = ""
        if isinstance(latest_val, (int, float)) and isinstance(prev.get("value", 0), (int, float)):
            diff = latest_val - prev["value"]
            if abs(diff) > 0.0001:
                arrow = "↑" if diff > 0 else "↓"
                change = f"{arrow} {abs(diff):.4f}"
        
        # 匹配知识模块
        matched_kn = []
        for keyword, kn_list in knowledge_map.items():
            if keyword in name:
                matched_kn.extend(kn_list)
        
        if not matched_kn:
            matched_kn = ["汇率理论"]
        
        item = {
            "name": name,
            "latest_value": str(latest_val),
            "change": change,
            "description": ind.get("description", ""),
        }
        
        print(f"  [macro] 加工: {name} (最新: {latest_val})")
        interpretation = process_macro_data(item, list(set(matched_kn)))
        
        if interpretation:
            interpretations[name] = interpretation
            interpretations[name]["_latest_value"] = str(latest_val)
            interpretations[name]["_change"] = change
        
        time.sleep(0.5)  # 避免API限流
    
    # 保存到 macro_data.json 中
    macro["ai_interpretations"] = {
        "generated_at": datetime.now().isoformat(),
        "indicators": interpretations,
    }
    
    with open(macro_path, "w", encoding="utf-8") as f:
        json.dump(macro, f, ensure_ascii=False, indent=2)
    
    print(f"\n[macro] 加工完成: {len(interpretations)} 项指标的解读已保存")
    return macro


def process_hotspots_batch():
    """批量加工热点数据"""
    hotspots_path = DATA_DIR / "hotspots_raw.json"
    if not hotspots_path.exists():
        print("[hotspots] hotspots_raw.json 不存在，跳过")
        return None
    
    with open(hotspots_path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    
    items = raw.get("raw_items", [])
    if not items:
        print("[hotspots] 没有原始热点数据")
        return None
    
    processed = []
    for item in items[:10]:  # 每次最多处理10条
        title = item.get("title", "")
        print(f"  [hotspots] 加工: {title[:40]}...")
        
        result = process_hotspot_item(item)
        if result:
            result["_source"] = item.get("source", "")
            result["_professor"] = item.get("professor", "")
            result["_original_title"] = title
            processed.append(result)
        
        time.sleep(0.5)
    
    # 构建 hot_topics.json
    sections = []
    for i, p in enumerate(processed, 1):
        priority = p.get("priority", "★★")
        sections.append({
            "id": f"auto_{i}",
            "title": p.get("title", ""),
            "content": p.get("summary", ""),
        })
    
    hot_topics = {
        "id": "auto_generated",
        "title": "学术动态追踪",
        "subtitle": "AI自动生成的最新学术热点与考点解读",
        "date": datetime.now().strftime("%Y-%m-%d"),
        "source": "AI自动采集+加工",
        "overview": f"本期共追踪 {len(processed)} 个学术热点，覆盖 {len(set(p.get('_professor','') for p in processed))} 位导师的最新研究成果。",
        "sections": [
            {
                "id": "summary",
                "title": "本期热点一览",
                "content": "\n".join([f"{i+1}. [{p.get('priority','★★')}] {p.get('title','')} — {p.get('_professor','')} ({p.get('_source','')})" for i, p in enumerate(processed)]),
            },
        ] + [
            {
                "id": f"detail_{i}",
                "title": f"{p.get('priority','★★')} {p.get('title','')}",
                "content": f"【来源】{p.get('_source','')} | 导师: {p.get('_professor','')}\n\n"
                          f"【核心观点】{p.get('summary','')}\n\n"
                          f"【考试关联】{p.get('exam_relevance','')}\n\n"
                          f"【关联知识点】{', '.join(p.get('related_topics',[]))}\n\n"
                          f"【所属模块】{p.get('category','综合')}",
            }
            for i, p in enumerate(processed, 1)
        ],
    }
    
    output_path = DATA_DIR / "hot_topics.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(hot_topics, f, ensure_ascii=False, indent=2)
    
    print(f"\n[hotspots] 加工完成: {len(processed)} 条热点已生成")
    return hot_topics


def main():
    key = get_api_key()
    if not key:
        print("=" * 60)
        print("API Key 未找到（环境变量或index.html中均未设置）")
        print("=" * 60)
        return 1
    
    print("=" * 60)
    print("AI 智能加工")
    print(f"模型: {MIMO_MODEL}")
    print(f"运行时间: {datetime.now().isoformat()}")
    print("=" * 60)
    
    # 1. 加工宏观数据
    print("\n[1/2] 加工宏观数据趋势解读...")
    process_macro_data_batch()
    
    # 2. 加工热点数据
    print("\n[2/2] 加工热点论文...")
    process_hotspots_batch()
    
    print("\n" + "=" * 60)
    print("AI 加工全部完成")
    print("=" * 60)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
