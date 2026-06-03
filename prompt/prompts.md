# 所有 system prompt 固定不变，触发 Anthropic prompt cache

SYSTEM = """你是一位资深中国民事诉讼案件文件信息提取助手。
规则：
1. 只提取文件中明确存在的信息，不推断、不补全、不评价
2. 严格输出 JSON，不加任何解释文字
3. 无法识别的字段填 null
4. 金额统一用数字（元），日期统一用 YYYY-MM-DD"""

# 按目录语义关键词路由到对应 prompt
PROMPTS = {
    "legal": {
        "keywords": ["判决", "裁定", "诉状", "起诉", "申请书", "笔录", "民申", "民初", "民终"],
        "user_tmpl": """文件路径：{path}
文件内容：
{content}

提取以下字段输出JSON：
{{
  "type": "文书类型",
  "case_no": "案号",
  "court": "法院名称",
  "date": "日期",
  "plaintiff": "原告/申请人",
  "defendant": "被告/被申请人",
  "claims": ["诉讼请求列表"],
  "facts_summary": "认定事实摘要(≤300字)",
  "verdict": "裁判结果",
  "legal_basis": ["法律依据"],
  "key_points": ["对李海有利的关键点", "对李海不利的关键点"]
}}"""
    },

    "financial": {
        "keywords": ["工资", "流水", "转账", "收据", "房租", "房贷", "还款", "存款", "付款", "首款", "尾款", "保姆"],
        "user_tmpl": """文件路径：{path}
凭证类型提示：{dir_name}
文件内容：
{content}

提取以下字段输出JSON（若为多条记录则输出数组）：
{{
  "type": "凭证类型",
  "date": "日期",
  "amount": 金额数字,
  "direction": "收入/支出",
  "payer": "付款方",
  "payee": "收款方",
  "account_hint": "账号尾号或账户特征",
  "purpose": "用途/备注"
}}"""
    },

    "chat": {
        "keywords": ["聊天", "微信", "沟通", "记录", "胁迫", "威胁", "苛刻"],
        "user_tmpl": """文件路径：{path}
文件内容：
{content}

只提取涉及【房产/财产/孩子/协议/威胁/承诺/违约】的对话，其余忽略。
输出JSON：
{{
  "type": "聊天记录",
  "time_range": "时间范围",
  "speakers": ["发言人列表"],
  "key_dialogues": [
    {{"time": "时间", "speaker": "说话人", "content": "内容", "topic": "涉及主题"}}
  ]
}}"""
    },

    "contract": {
        "keywords": ["合同", "协议", "离婚协议", "购房", "贷款", "装修", "买卖"],
        "user_tmpl": """文件路径：{path}
文件内容：
{content}

提取以下字段输出JSON：
{{
  "type": "合同类型",
  "sign_date": "签订日期",
  "party_a": "甲方",
  "party_b": "乙方",
  "amount": 标的金额数字,
  "property_address": "房产地址(如有)",
  "key_terms": ["核心条款(≤5条)"],
  "performance_status": "履约状态(已履行/未履行/部分履行/未知)"
}}"""
    },

    "proof": {
        "keywords": ["证明", "残疾", "住院", "入职", "户口", "房产证", "物业", "体检", "结婚证", "离婚证", "签证", "护照"],
        "user_tmpl": """文件路径：{path}
证明类型提示：{dir_name}
文件内容：
{content}

提取以下字段输出JSON：
{{
  "type": "证明类型",
  "issuer": "出具机构",
  "date": "日期",
  "subject": "证明对象(人名)",
  "core_fact": "核心证明内容(≤100字)",
  "key_values": {{"金额/数值描述": "值"}}
}}"""
    },

    "general": {
        "keywords": [],
        "user_tmpl": """文件路径：{path}
目录提示：{dir_name}
文件内容：
{content}

提取文件中所有关键事实，输出JSON：
{{
  "type": "文件类型",
  "date": "日期(如有)",
  "parties": ["涉及人员"],
  "key_facts": ["关键事实列表"],
  "amounts": [{{"描述": "", "金额": 数字}}],
  "raw_summary": "内容摘要(≤200字)"
}}"""
    }
}


def route(file_path: str, dir_name: str) -> str:
    """根据路径关键词判断文书类型，按命中数量取最高分"""
    combined = (file_path + dir_name).replace("/", "")
    scores = {}
    for ptype, cfg in PROMPTS.items():
        if ptype == "general":
            continue
        scores[ptype] = sum(1 for kw in cfg["keywords"] if kw in combined)
    best = max(scores, key=lambda k: scores[k])
    return best if scores[best] > 0 else "general"
