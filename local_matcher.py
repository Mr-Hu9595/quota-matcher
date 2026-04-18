"""
本地关键词匹配模块
功能：不使用API，直接通过关键词匹配定额
参考：
  - 3万吨CHDM项目 + 电气/电信全套预算表 (2026年4月)
  - 《河南省房屋建筑与装饰工程预算定额》《河南省通用安装工程预算定额》《河南省市政工程预算定额》综合解释 (HA 2016)

★ 定额选用规则（来源：河南省定额综合解释）：
  【第四册 电气设备安装工程】
  - 电缆（电力电缆）：按"单芯最大截面"套定额（如4×240+1×120 → 240mm²）
  - 电缆（控制电缆）：按"芯数"套定额（如10×1.5 → 10芯）
  - 五芯以上电缆敷设：五芯×1.15，六芯×1.3，每增一芯+15%（定额按三芯编制）
  - 电缆头制作安装：三芯及三芯连地编制；五芯头×1.15，六芯头×1.3，每增一芯+15%；单芯头×0.3
  - 地下室安装工程：定额人工费×1.12
  - 管井内安装工程：定额人工费×1.16
  - 电缆π接箱：按室内端子箱套用
  - 总等电位箱：按半周长0.5m成套配电箱×0.4
  - 避雷引下线与避雷网跨接：已综合，不另计
  - 凿槽/凿孔(洞)：按第十册执行
  - 多芯导线：折合成单芯截面套用
  - 带开关插座：按插座种类套单相/三相插座
  【第五册 建筑智能化】
  - 智能化配管工程由总包施工时，插座底盒/过线盒按第四册接线盒子目执行
  【第九册 消防工程】
  - 消火栓按钮（无手动启泵系统）：按火灾报警按钮执行
"""

import os
import re
from typing import List, Dict, Optional


class LocalMatcher:
    """本地关键词匹配器（改进版）"""

    # ============================================================
    # 精准材料/设备→定额映射表
    # 参考：3万吨CHDM项目 + 电信全套预算表 + 河南省定额综合解释
    # 格式: {材料名: 定额编号} 或 {材料名: {规格: 定额编号}}
    # ============================================================
    MATERIAL_QUOTA_MAP = {

        # ========== 钢管敷设 (4-12系列) ==========
        # 明配 - 镀锌钢管 砖、混凝土结构
        "镀锌钢管": {
            "DN20": "4-12-24", "DN25": "4-12-25", "DN32": "4-12-26",
            "DN40": "4-12-27", "DN50": "4-12-28", "DN80": "4-12-30", "DN100": "4-12-31"
        },
        "热镀锌钢管": {
            "DN20": "4-12-24", "DN25": "4-12-25", "DN32": "4-12-26",
            "DN40": "4-12-27", "DN50": "4-12-28", "DN80": "4-12-30", "DN100": "4-12-31"
        },
        # 暗配 - 镀锌钢管
        "镀锌钢管暗配": {
            "DN20": "4-12-35", "DN25": "4-12-36", "DN32": "4-12-37",
            "DN40": "4-12-38", "DN50": "4-12-39", "DN80": "4-12-41", "DN100": "4-12-42"
        },
        # 防爆钢管 明配
        "防爆钢管": {
            "DN20": "4-12-78", "DN25": "4-12-79", "DN32": "4-12-80",
            "DN40": "4-12-81", "DN50": "4-12-82", "DN65": "4-12-83",
            "DN80": "4-12-84", "DN100": "4-12-85"
        },
        # 其他管材
        "刚性阻燃管": "4-12-130",
        "半硬质塑料管": "4-12-152",
        "PVC管": "4-12-152",
        "埋地钢管": {"DN150": "4-12-76"},

        # ========== 电缆敷设 (4-9系列) ==========
        # 电力电缆 室内敷设 铜芯
        "电力电缆": {
            "≤10mm²": "4-9-159", "≤16mm²": "4-9-160",
            "≤35mm²": "4-9-161", "≤50mm²": "4-9-162",
            "≤70mm²": "4-9-163", "≤120mm²": "4-9-164", "≤240mm²": "4-9-165",
            "10kV-3×300": "4-9-166"
        },
        # 控制电缆 室内敷设
        "控制电缆": {"≤6芯": "4-9-310", "≤14芯": "4-9-311", "≤24芯": "4-9-312"},
        # 直埋电缆
        "直埋电缆": "4-9-127",
        # 电缆终端头 - 电力电缆 1kV干包式
        "电力电缆终端头": {
            "≤10mm²": "4-9-244", "≤16mm²": "4-9-245", "≤35mm²": "4-9-246",
            "≤50mm²": "4-9-247", "≤70mm²": "4-9-248", "≤120mm²": "4-9-249", "≤240mm²": "4-9-250"
        },
        # 电力电缆终端头 10kV热缩式
        "10kV电力电缆终端头": {"≤120mm²": "4-9-277", "≤400mm²": "4-9-279"},
        # 控制电缆终端头
        "控制电缆终端头": {"≤6芯": "4-9-320", "≤14芯": "4-9-321"},
        # 电缆防火
        "防火包": "4-9-331",
        "防火堵料": "4-9-332",
        "防火涂料": "4-9-333",
        # 穿线
        "穿照明线": "4-13-5",
        "穿动力线": "4-13-29",

        # ========== 电信/网络线缆 (5-2系列) ==========
        "网线": "5-2-42",
        "超五类网线": "5-2-42",
        "双绞线": "5-2-42",
        "超五类双绞线": "5-2-42",
        "双绞线测试": "5-2-107",
        "光缆": "5-2-45",
        "光缆测试": "5-2-108",
        "光纤链路衰减测试": "11-8-49",
        "光纤熔接": "5-2-92",
        "尾纤": "5-2-102",
        "光纤跳线": "5-2-60",
        "光缆终端盒": {"≤12芯": "5-2-96", "≤24芯": "5-2-97"},
        "信息插座": {"双口": "5-2-85", "单口": "5-2-84"},
        "光电转换器": "11-9-65",

        # ========== 桥架/线槽 (4-9系列) ==========
        "桥架": "4-9-65",
        "槽式桥架": {"≤400mm": "4-9-65", "≤600mm": "4-9-66", "≤800mm": "4-9-67"},
        "梯式桥架": {"≤500mm": "4-9-72", "≤800mm": "4-9-73"},
        "电缆桥架": "4-9-65",
        "桥架支撑架": {"制作": "4-7-3", "安装": "4-7-4"},

        # ========== 接线盒/穿线盒 (4-13系列) ==========
        "接线盒": {"暗装": "4-13-179", "明装普通": "4-13-180", "明装防爆": "4-13-181"},
        "开关盒": "4-13-179",
        "插座盒": "4-13-179",
        "穿线盒": "6-8-97",  # 金属穿线盒 防爆型
        "挠性管": {"普通": "6-8-98", "防爆": "6-8-99"},
        "防爆胶泥": "6-8-102",

        # ========== 金属结构件 (3-6/4-7系列) ==========
        "方管": {"制作": "3-6-58", "安装": "3-6-60"},
        "槽钢": {"制作": "3-6-58", "安装": "3-6-60"},
        "角钢": {"制作": "3-6-58", "安装": "3-6-60"},
        "扁铁": {"制作": "3-6-58", "安装": "3-6-60"},
        "扁钢": {"制作": "3-6-58", "安装": "3-6-60"},
        "花纹钢板": {"制作": "3-6-58", "安装": "3-6-60"},
        "钢板": {"制作": "3-6-58", "安装": "3-6-60"},
        "金属结构件": {"制作": "3-6-58", "安装": "3-6-60"},
        "监控立柱": {"制作": "3-6-58", "安装": "3-6-60"},
        "基础槽钢": "4-7-1",
        "铁构件": {"制作": "4-7-5", "安装": "4-7-6"},

        # ========== 配电箱/柜 (4-2系列) ==========
        "配电箱": {"≤0.5m": "4-2-75", "≤1.0m": "4-2-76", "≤1.5m": "4-2-77", "≤2.5m": "4-2-78", "落地式": "4-2-74"},
        "控制箱": {"≤0.5m": "4-2-75", "≤1.0m": "4-2-76", "≤1.5m": "4-2-77", "≤2.5m": "4-2-78"},
        "动力箱": "4-2-74",
        "开关箱": "4-2-76",
        "操作柱": "4-2-75",
        "配电柜": "4-2-72",
        "配电屏": "4-2-72",
        "高压配电柜": "4-2-61",
        "UPS电源": {"单相≤30kVA": "4-5-49", "三相≤100kVA": "4-5-50"},
        "UPS": {"单相≤30kVA": "4-5-49", "三相≤100kVA": "4-5-50"},
        "蓄电池": {"铅酸≤200Ah": "4-5-13", "免维护100Ah": "4-5-26", "免维护200Ah": "4-5-27", "免维护300Ah": "4-5-28"},
        "蓄电池充放电": {"≤100Ah": "4-5-35", "≤300Ah": "4-5-37"},
        "蓄电池支架": "4-5-3",
        "GPS时钟": "4-2-103",
        "配电自动化": {"子站柜": "4-2-104", "调试": "4-2-105"},

        # ========== 电动机 (4-6系列) ==========
        "异步电动机": {"≤3kW": "4-6-17", "≤13kW": "4-6-18", "≤30kW": "4-6-19", "≤100kW": "4-6-20"},
        "防爆电动机": {"≤3kW": "4-6-27", "≤13kW": "4-6-28", "≤30kW": "4-6-29", "≤100kW": "4-6-30"},
        "同步电动机": {"≤100kW": "4-6-25"},
        "大中型电机": {"≤5t": "4-6-36", "≤20t": "4-6-38"},
        "微型电机": "4-6-41",
        "电动葫芦": "4-6-16",

        # ========== 电动机调试 (4-17系列) ==========
        "电机调试": {
            "低压笼型电磁控制": "4-17-114", "低压笼型过流保护": "4-17-116",
            "低压绕线型": "4-17-118", "高压一次设备≤350kW": "4-17-120",
            "高压一次设备≤1600kW": "4-17-122"
        },
        "变频电机调试": {
            "≤3kW": "4-17-137", "≤13kW": "4-17-138", "≤30kW": "4-17-139",
            "≤50kW": "4-17-140", "≤150kW": "4-17-141", "高压≤2000kW": "4-17-144"
        },

        # ========== 变压器 (4-1系列) ==========
        "干式变压器": {"≤2000kVA": "4-1-13"},

        # ========== 母线 (4-3系列) ==========
        "铜母线": {"≤360mm²": "4-3-21", "≤800mm²": "4-3-22", "≤1000mm²单片": "4-3-23", "≤1000mm²双片": "4-3-25"},
        "母线槽": {"≤1250A": "4-3-110", "≤4000A": "4-3-112"},
        "母线槽始端箱": "4-3-122",

        # ========== 照明灯具 (4-14系列) ==========
        "吸顶灯": "4-14-2",
        "标志灯": {"吸顶": "4-14-154", "壁装": "4-14-156"},
        "诱导灯": {"吸顶": "4-14-154", "壁装": "4-14-156"},
        "防尘防水灯": {"直杆式": "4-14-218", "弯杆式": "4-14-219"},
        "防爆灯": {"直杆式": "4-14-236", "弯杆式": "4-14-237"},
        "防爆LED灯": "4-14-240",
        "防爆荧光灯": "4-14-240",
        "应急灯": "4-14-240",
        "安全灯": "4-14-235",
        "路灯": {"防爆": "4-14-283", "普通": "4-14-283"},
        "高杆灯": {"≤20m": "4-14-302"},
        "路灯杆": {"≤10m": "4-14-357"},
        "跷板开关": "4-14-378",
        "防爆开关": "4-14-384",
        "防爆插座": "4-14-408",

        # ========== 电气调试 (4-17系列) ==========
        "变压器调试": {"≤2000kVA": "4-17-23"},
        "输配电调试": {"≤1kV": "4-17-28", "≤10kV带断路器": "4-17-30", "直流≤500V": "4-17-32"},
        "保护装置调试": "4-17-40",
        "备用电源自投": "4-17-41",
        "重合闸调试": "4-17-44",
        "无功补偿调试": {"≤1kV": "4-17-63", "≤10kV": "4-17-64"},
        "UPS调试": {"≤30kVA": "4-17-57", ">100kVA": "4-17-59"},
        "变电站调试": {"≤10kV": "4-17-192"},
        "微机监控调试": "4-17-166",
        "电压互感器压降测试": "4-17-204",

        # ========== 避雷/接地 (4-10系列) ==========
        "避雷网": {"沿混凝土块": "4-10-44", "沿折板支架": "4-10-45"},
        "避雷引下线": "4-10-43",
        "接地母线": {"户内": "4-10-56", "户外": "4-10-57"},
        "接地绞线": "4-10-58",
        "接地极": {"圆钢": "4-10-52", "铜板": "4-10-54"},
        "接地跨接": "4-10-60",
        "接地模块": "4-10-73",
        "接地系统调试": "4-10-79",
        # 等电位连接 (5-7系列) - 用于黄绿双色线等
        "等电位连接": "5-7-65",
        "接地跨接线": "5-7-65",  # 注意：5-7-65是等电位跨接，4-10-60是构架接地
        "黄绿双色线": "5-7-65",
        "总等电位箱": "4-2-75",  # 按半周长0.5m成套配电箱×0.4（人工系数）
        "电缆π接箱": "4-4-12",    # 按室内端子箱套用（综合解释第四册）
        "π接箱": "4-4-12",       # 同上

        # ========== 监控设备 (5-6系列) ==========
        "摄像机": {"普通": "5-6-78", "半球": "5-6-79", "球机": "5-6-80", "防爆": "5-6-82", "云台": "5-6-84"},
        "摄像头": "5-6-82",
        "监控摄像机": {"普通": "5-6-78", "防爆": "5-6-82"},
        "防爆摄像机": "5-6-82",
        "半球摄像机": "5-6-79",
        "球型摄像机": "5-6-80",
        "云台摄像机": "5-6-84",
        "摄像机电源": "5-6-113",
        "摄像机支架": {"壁式": "5-6-101", "立柱式": "5-6-103"},
        "摄像机防护罩": {"全天候": "5-6-99", "防爆": "5-6-100"},
        "视频监控调试": {"4路": "6-5-50", "9路": "6-5-51", "16路": "6-5-52"},

        # ========== 消防报警 (9-4/9-5系列) ==========
        "感烟探测器": "9-4-1",
        "火焰探测器": "9-4-4",
        "火灾报警按钮": "9-4-9",
        "防爆报警按钮": "9-4-9",
        "消火栓按钮": "9-4-10",
        "声光报警器": "9-4-12",
        "防爆声光": "9-4-12",
        "报警模块": {"单输入": "9-4-23", "单输入单输出": "9-4-27", "多输入多输出": "9-4-28"},
        "模块箱": {"普通": "9-4-29", "防爆": "9-4-29"},
        "火灾报警控制器": "9-4-70",
        "火灾报警主机": {"壁挂64点": "9-4-66", "落地256点": "9-4-68"},
        "报警系统调试": {"≤64点": "9-5-1", "≤256点": "9-5-3"},
        "防火卷帘门调试": "9-5-14",
        "防火门调试": "9-5-15",
        "电动防火阀调试": "9-5-16",
        "消防风机调试": "9-5-18",
        "消防水泵调试": "9-5-19",
        "气体灭火调试": "9-5-26",

        # ========== 扬声器/广播 (9-5/5-5系列) ==========
        "扬声器": "9-5-9",
        "音箱": "9-5-9",
        "广播喇叭": "9-5-9",
        "防爆音箱": "5-5-73",
        "电话插孔": "9-5-9",
        "通信分机": "9-5-10",

        # ========== 机柜/交换机 (5-1/5-2系列) ==========
        "机柜": {"落地式": "5-2-20", "墙挂式防爆": "5-2-21"},
        "DCS柜": "5-2-20",
        "控制柜": "5-2-20",
        "配电柜": "4-2-72",
        "交换机": {"≤24口": "5-1-86", "插槽式>4槽": "5-1-89"},
        "服务器": {"2U": "5-1-95"},
        "防火墙": "5-1-81",
        "磁盘阵列": "5-1-41",
        "网络交换机": "5-1-86",

        # ========== 仪表/阀门 (6-1/6-2系列) ==========
        "压力开关": "6-1-53",
        "电动蝶阀": "6-2-94",
        "多通电动阀": "6-2-95",
        "多通电磁阀": "6-2-96",
        "仪表立柱": "6-10-27",
        "防雨罩": "6-10-49",

        # ========== 端子/压接 (4-4系列) ==========
        "接线端子": "4-4-26",
        "压接端子": {"≤16mm²": "4-4-26", "≤35mm²": "4-4-27", "≤70mm²": "4-4-28", "≤120mm²": "4-4-29"},
        "端子排": "4-4-26",
        "有端子接线": "4-4-16",
        "励磁屏": "4-4-56",
        "直流馈电屏": "4-4-57",

        # ========== 其他设备 ==========
        "浪涌保护器": "12-11-44",
        "光纤收发器": "11-9-65",
        "光端机": "11-9-65",
        "千兆收发器": "11-9-65",
        "百兆收发器": "11-9-65",
        "水泵": "1-8-97",
        "计量泵": "1-8-97",
        "潜水泵": "1-8-98",
        "风机": "1-8-50",
        "皮带秤": "2-5-17",

        # ========== 软件/系统 ==========
        "网管软件": "6-6-33",
        "管理软件": "6-6-33",
        "系统软件": "5-1-116",
    }

    def __init__(self, quota_data: List[Dict], use_websearch: bool = True):
        """初始化本地匹配器"""
        self.quota_data = quota_data
        self.all_codes = [q["code"] for q in quota_data]
        self.use_websearch = use_websearch
        self.api_key = os.environ.get("MINIMAX_API_KEY")
        self.search_api_url = "https://api.minimax.chat/v1/search"
        self._build_quota_index()

    def _build_quota_index(self):
        """构建定额索引，加速搜索"""
        self.quota_by_code = {q["code"]: q for q in self.quota_data}
        # 按名称关键词建立索引
        self.quota_by_keyword = {}
        for q in self.quota_data:
            keywords = self._extract_keywords(q["name"])
            for kw in keywords[:5]:
                if kw not in self.quota_by_keyword:
                    self.quota_by_keyword[kw] = []
                self.quota_by_keyword[kw].append(q)

    def match(self, item_name: str, quantity: float = None, unit: str = None) -> Dict:
        """
        匹配单个清单项目

        Args:
            item_name: 清单项目名称
            quantity: 工程量（可选）
            unit: 单位（可选）

        Returns:
            Dict: 匹配结果
        """
        # 优先精确匹配（材料+规格）
        exact_match = self._exact_match(item_name, unit)
        if exact_match:
            return exact_match

        # 模糊关键词匹配
        fuzzy_match = self._fuzzy_match(item_name, unit)
        if fuzzy_match:
            return fuzzy_match

        # 从定额库中搜索
        relevant = self._find_relevant_quotas(item_name, unit)
        if relevant:
            best = relevant[0]
            # 如果匹配不确定且启用了联网搜索，尝试联网搜索
            if self.use_websearch and self.api_key:
                search_result = self._web_search_match(item_name, relevant)
                if search_result:
                    return search_result
            return {
                "code": best["code"],
                "name": best["name"],
                "unit": best["unit"],
                "confidence": "medium",
                "note": "定额库模糊匹配，建议人工确认",
                "need_confirm": True
            }

        return {
            "code": "",
            "name": f"{item_name}（待人工确认）",
            "unit": unit or "",
            "confidence": "low",
            "note": "未找到相关定额，请人工匹配",
            "need_confirm": True
        }

    def _exact_match(self, item_name: str, unit: str = None) -> Optional[Dict]:
        """精确匹配（基于MATERIAL_QUOTA_MAP经验映射表）"""
        item_lower = item_name.lower()
        item_upper = item_name.upper()

        # ============================================
        # 钢管规格匹配 (DNxx格式，支持 DN25、DN≤25、≤25等多种格式)
        # 注意：必须先于通用映射表查找，避免被"防爆"等短词误匹配
        # ============================================
        if "管" in item_lower:
            # 提取管径
            match = re.search(r'DN[≤\s]*(\d+)', item_lower, re.IGNORECASE)
            if match:
                dn = f"DN{match.group(1)}"
                # 防爆钢管 (必须先检查，因为"防爆"会误匹配其他条目)
                if "防爆" in item_lower and ("钢管" in item_lower or "管" in item_lower):
                    pipe_map = self.MATERIAL_QUOTA_MAP.get("防爆钢管", {})
                    if dn in pipe_map:
                        quota = self.quota_by_code.get(pipe_map[dn])
                        if quota:
                            return {"code": quota["code"], "name": quota["name"], "unit": quota["unit"], "confidence": "high", "note": f"精确匹配（防爆钢管{dn}）", "need_confirm": False}
                # 镀锌/热镀锌钢管
                elif "镀锌" in item_lower or "热镀锌" in item_lower:
                    for pipe_type in ["热镀锌钢管", "镀锌钢管"]:
                        pipe_map = self.MATERIAL_QUOTA_MAP.get(pipe_type, {})
                        if dn in pipe_map:
                            quota = self.quota_by_code.get(pipe_map[dn])
                            if quota:
                                return {"code": quota["code"], "name": quota["name"], "unit": quota["unit"], "confidence": "high", "note": f"精确匹配（{pipe_type}{dn}）", "need_confirm": False}
                # 埋地钢管
                elif "埋地" in item_lower:
                    pipe_map = self.MATERIAL_QUOTA_MAP.get("埋地钢管", {})
                    if dn in pipe_map:
                        quota = self.quota_by_code.get(pipe_map[dn])
                        if quota:
                            return {"code": quota["code"], "name": quota["name"], "unit": quota["unit"], "confidence": "high", "note": f"精确匹配（埋地钢管{dn}）", "need_confirm": False}

        # ============================================
        # 通用映射表查找 - 仅用于无规格参数的直接匹配
        # 避免短关键词误匹配，按关键词长度降序排列
        # ============================================
        direct_matches = [
            # 特殊设备/系统 - 完整名称匹配
            ("感烟探测器", "9-4-1"),
            ("火焰探测器", "9-4-4"),
            ("感温探测器", "9-4-2"),
            ("火灾报警按钮", "9-4-9"),
            ("声光报警器", "9-4-12"),
            ("消火栓报警按钮", "9-4-10"),
            ("消防炮控制箱", "9-4-39"),
            ("火灾报警控制器", "9-4-70"),
            ("报警模块 单输入", "9-4-23"),
            ("报警模块 单输入单输出", "9-4-27"),
            ("报警模块 多输入多输出", "9-4-28"),
            ("模块箱", "9-4-29"),
            ("模块箱 防爆", "9-4-29"),
            ("报警主机", "9-4-66"),
            ("火灾报警主机", "9-4-66"),
            ("火灾报警联动一体机", "9-4-68"),
            ("自动报警系统调试", "9-5-1"),
            ("防火卷帘门调试", "9-5-14"),
            ("防火门调试", "9-5-15"),
            ("电动防火阀调试", "9-5-16"),
            ("消防风机调试", "9-5-18"),
            ("消防水泵调试", "9-5-19"),
            ("气体灭火调试", "9-5-26"),
            # 广播/扬声器
            ("广播喇叭及音箱", "9-5-9"),
            ("防爆音箱", "5-5-73"),
            ("通信分机", "9-5-10"),
            # 摄像机/监控
            ("云台摄像机", "5-6-84"),
            ("摄像机电源", "5-6-113"),
            ("摄像机支架 壁式", "5-6-101"),
            ("摄像机支架 立柱式", "5-6-103"),
            ("摄像机防护罩 全天候", "5-6-99"),
            ("摄像机防护罩 防爆", "5-6-100"),
            # 接地/避雷
            ("避雷网", "4-10-44"),
            ("避雷网 沿混凝土块", "4-10-44"),
            ("避雷网 沿折板支架", "4-10-45"),
            ("避雷引下线", "4-10-43"),
            ("接地母线", "4-10-56"),
            ("接地母线 户内", "4-10-56"),
            ("接地母线 户外", "4-10-57"),
            ("接地绞线", "4-10-58"),
            ("接地极", "4-10-52"),
            ("接地极 圆钢", "4-10-52"),
            ("接地极 铜板", "4-10-54"),
            ("接地跨接 构架", "4-10-60"),
            ("接地模块", "4-10-73"),
            ("接地系统调试", "4-10-79"),
            # 变压器
            ("干式变压器", "4-1-13"),
            # 端子/压接
            ("压接端子 ≤16mm²", "4-4-26"),
            ("压接端子 ≤35mm²", "4-4-27"),
            ("压接端子 ≤70mm²", "4-4-28"),
            ("压接端子 ≤120mm²", "4-4-29"),
            ("有端子接线", "4-4-16"),
            ("励磁屏", "4-4-56"),
            ("直流馈电屏", "4-4-57"),
            # 照明
            ("吸顶灯", "4-14-2"),
            ("吸顶灯具", "4-14-2"),
            ("标志灯 吸顶", "4-14-154"),
            ("标志灯 壁装", "4-14-156"),
            ("诱导灯 吸顶", "4-14-154"),
            ("诱导灯 壁装", "4-14-156"),
            ("防尘防水灯 直杆式", "4-14-218"),
            ("防尘防水灯 弯杆式", "4-14-219"),
            ("防爆灯", "4-14-236"),
            ("防爆灯 直杆式", "4-14-236"),
            ("防爆灯 弯杆式", "4-14-237"),
            ("防爆LED灯", "4-14-240"),
            ("防爆荧光灯", "4-14-240"),
            ("LED灯", "4-14-240"),
            ("应急灯", "4-14-240"),
            ("安全灯", "4-14-235"),
            ("路灯", "4-14-283"),
            ("防爆路灯", "4-14-283"),
            ("高杆灯", "4-14-302"),
            ("路灯杆", "4-14-357"),
            ("跷板开关", "4-14-378"),
            ("防爆开关", "4-14-384"),
            ("配电箱", "4-2-75"),
            ("防爆插座", "4-14-408"),
            # 蓄电池
            ("蓄电池 铅酸", "4-5-13"),
            ("蓄电池 免维护", "4-5-26"),
            ("蓄电池充放电", "4-5-35"),
            ("蓄电池支架", "4-5-3"),
            # 仪表/阀门
            ("压力开关", "6-1-53"),
            ("电动蝶阀", "6-2-94"),
            ("多通电动阀", "6-2-95"),
            ("多通电磁阀", "6-2-96"),
            ("仪表立柱", "6-10-27"),
            ("防雨罩", "6-10-49"),
            # 电气调试
            ("变压器调试", "4-17-23"),
            ("输配电调试 ≤1kV", "4-17-28"),
            ("输配电调试 ≤10kV", "4-17-30"),
            ("保护装置调试", "4-17-40"),
            ("备用电源自投", "4-17-41"),
            ("重合闸调试", "4-17-44"),
            ("无功补偿调试 ≤1kV", "4-17-63"),
            ("无功补偿调试 ≤10kV", "4-17-64"),
            ("变电站调试", "4-17-192"),
            ("微机监控调试", "4-17-166"),
            ("电压互感器压降测试", "4-17-204"),
            # 电缆防火
            ("防火包", "4-9-331"),
            ("防火堵料", "4-9-332"),
            ("防火涂料", "4-9-333"),
            # 穿线
            ("穿照明线", "4-13-5"),
            ("穿动力线", "4-13-29"),
            # 其他
            ("浪涌保护器", "12-11-44"),
            ("GPS时钟", "4-2-103"),
            ("配电自动化 子站柜", "4-2-104"),
            ("配电自动化 调试", "4-2-105"),
            ("水泵", "1-8-97"),
            ("计量泵", "1-8-97"),
            ("潜水泵", "1-8-98"),
            ("风机", "1-8-50"),
            ("皮带秤", "2-5-17"),
            ("电动葫芦", "4-6-16"),
            ("微型电机", "4-6-41"),
            ("大中型电机 ≤5t", "4-6-36"),
            ("大中型电机 ≤20t", "4-6-38"),
            ("球机", "5-6-80"),
            ("扁铁", "3-6-58"),
            ("扁钢", "3-6-58"),
            ("软件系统", "5-1-116"),
            ("防火墙", "5-1-81"),
            ("磁盘阵列", "5-1-41"),
            ("桥架", "4-9-65"),
            ("桥架安装", "4-9-65"),
            ("动力箱", "4-2-74"),
            ("开关箱", "4-2-76"),
            ("同步电动机检查接线", "4-6-22"),
            ("角钢", "3-6-60"),
            # ========== 配电箱/操作柱 ==========
            ("操作柱", "4-2-75"),
            ("路灯接线箱", "4-2-75"),
            ("双切配电箱", "4-2-77"),
            ("双切电源配电箱", "4-2-77"),
            ("动力配电箱", "4-2-77"),
            ("动力箱", "4-2-74"),
            ("检修箱", "4-2-76"),
            # ========== 电动机 ==========
            ("电动机检查接线", "4-6-18"),
            ("异步电动机检查接线", "4-6-18"),
            ("防爆电动机检查接线", "4-6-28"),
            ("同步电动机检查接线", "4-6-25"),
            # ========== 开关/断路器 ==========
            ("空气断路器", "4-15-28"),
            ("自动空气断路器", "4-15-28"),
            ("微型断路器", "4-15-28"),
            # ========== 火灾报警 ==========
            ("感烟探测器", "9-4-1"),
            ("感温探测器", "9-4-2"),
            ("火焰探测器", "9-4-4"),
            ("火灾报警按钮", "9-4-9"),
            ("声光报警器", "9-4-12"),
            ("报警模块", "9-4-23"),
            ("模块箱", "9-4-29"),
            ("火灾报警控制器", "9-4-70"),
            ("火灾报警主机", "9-4-66"),
            ("火灾报警联动一体机", "9-4-68"),
            ("应急照明控制主机", "9-4-66"),
            ("消防炮控制箱", "9-4-39"),
            # ========== 监控系统 ==========
            ("硬盘录像机", "5-1-34"),
            ("数字硬盘录像机", "5-1-34"),
            ("监视器", "5-1-18"),
            ("摄像机", "5-6-78"),
            ("监控摄像机", "5-6-78"),
            ("防爆摄像机", "5-6-82"),
            ("枪机", "5-6-83"),
            ("半球摄像机", "5-6-79"),
            ("球型摄像机", "5-6-80"),
            ("云台摄像机", "5-6-84"),
            ("摄像机防护罩", "5-6-99"),
            ("摄像机支架", "5-6-101"),
            ("摄像机电源", "5-6-113"),
            ("主控键盘", "5-6-147"),
            ("视频监控系统调试", "6-5-50"),
            # ========== 网络设备 ==========
            ("交换机", "5-1-86"),
            ("网络交换机", "5-1-86"),
            ("汇聚交换机", "5-1-87"),
            ("服务器", "5-1-64"),
            ("台式电脑", "5-1-101"),
            ("计算机", "5-1-101"),
            # ========== 存储设备 ==========
            ("磁盘阵列", "5-1-41"),
            # ========== 防火墙 ==========
            ("防火墙", "5-1-81"),
            ("状态防火墙", "5-1-81"),
            # ========== 机柜 ==========
            ("机柜", "5-2-20"),
            ("安装机柜", "5-2-20"),
            ("配线架", "5-2-70"),
            ("光纤配线架", "5-2-89"),
            ("理线架", "5-2-70"),
            # ========== 电视系统 ==========
            ("电视墙", "5-4-3"),
            ("电视墙架", "5-4-3"),
            # ========== 天线 ==========
            ("定向天线", "11-10-HA17"),
            ("室内天线", "11-10-HA18"),
            # ========== 等电位连接 ==========
            ("等电位连接", "5-7-65"),
            ("接地汇流排", "5-7-63"),
            # ========== 测试 ==========
            ("光纤链路测试", "11-8-49"),
            ("光纤链路衰减测试", "11-8-49"),
            ("系统调试", "5-2-114"),
            ("视频系统调试", "5-5-214"),
            # ========== 阀门 ==========
            ("电动蝶阀", "6-2-94"),
            ("多通电动阀", "6-2-95"),
            # ========== 接地/避雷 ==========
            ("避雷网", "4-10-44"),
            ("避雷引下线", "4-10-43"),
            ("接地母线", "4-10-56"),
            ("接地绞线", "4-10-58"),
            ("接地极", "4-10-52"),
            ("接地模块", "4-10-73"),
            ("接地跨接线", "5-7-65"),
            # ========== 桥架/线槽 ==========
            ("桥架", "4-9-65"),
            ("梯式桥架", "4-9-72"),
            ("槽式桥架", "4-9-65"),
            ("桥架支撑架", "4-7-4"),
            # ========== 照明 ==========
            ("路灯", "4-14-283"),
            ("高杆灯", "4-14-302"),
            ("路灯杆", "4-14-357"),
            ("吸顶灯", "4-14-2"),
            ("标志灯", "4-14-154"),
            ("防爆灯", "4-14-236"),
            ("应急灯", "4-14-240"),
            ("LED灯", "4-14-240"),
            # ========== 通信 ==========
            ("扬声器", "9-5-9"),
            ("音箱", "9-5-9"),
            ("防爆音箱", "5-5-73"),
            ("广播", "9-5-9"),
            ("电话出线口", "5-8-HA15"),
            ("组线箱", "5-8-HA6"),
            ("程控交换机", "5-8-HA1"),
            # ========== 光纤/同轴 ==========
            ("大对数线缆", "5-2-30"),
            ("同轴电缆", "5-2-110"),
            ("视频同轴电缆", "5-2-110"),
            # ========== 其他 ==========
            ("浪涌保护器", "12-11-44"),
            ("金属软管", "4-12-173"),
            ("软管", "4-12-173"),
        ]

        for keyword, code in direct_matches:
            if keyword.lower() in item_lower:
                quota = self.quota_by_code.get(code)
                if quota:
                    return {
                        "code": quota["code"],
                        "name": quota["name"],
                        "unit": quota["unit"],
                        "confidence": "high",
                        "note": f"精确匹配（{keyword}）",
                        "need_confirm": False
                    }

        # ============================================
        # 电力/控制电缆芯数/截面匹配
        # ============================================
        # 提取芯数 (如 6芯, 14芯, 24芯)
        core_match = re.search(r'(\d+)芯', item_lower)
        # 提取截面 (如 10mm², 16mm², 截面≤10mm², 截面积≤120mm²)
        section_match = re.search(r'截[面积]*[≤\s]*(\d+)\s*mm', item_lower, re.IGNORECASE)
        # 从"n×m"格式提取电力电缆**最大单芯截面**，如"4×25+1×16"→取max(25,16)=25mm²
        power_cable_match = re.findall(r'(\d+)\s*[×x]\s*(\d+)', item_lower)
        # 从"n×m"格式提取控制电缆**芯数**（所有芯数之和），如"10×1.5"→10芯
        ctrl_cable_core_match = re.findall(r'(\d+)\s*[×x]\s*(\d+(?:\.\d+)?)', item_lower)

        if "终端头" in item_lower or "电缆头" in item_lower:
            # 电缆终端头匹配
            # ★ 电缆头规则（综合解释第四册）：定额按三芯编制，五芯×1.15、六芯×1.3、单芯×0.3
            if "10kV" in item_lower or "热缩" in item_lower:
                cable_map = self.MATERIAL_QUOTA_MAP.get("10kV电力电缆终端头", {})
                if core_match:
                    section = int(core_match.group(1))
                    for key, code in cable_map.items():
                        if "≤" in key:
                            max_val = int(re.search(r'(\d+)', key).group(1))
                            if section <= max_val:
                                quota = self.quota_by_code.get(code)
                                if quota:
                                    return {"code": quota["code"], "name": quota["name"], "unit": quota["unit"], "confidence": "high", "note": f"精确匹配（10kV电力电缆终端头）", "need_confirm": False}
            elif "控制电缆" in item_lower:
                cable_map = self.MATERIAL_QUOTA_MAP.get("控制电缆终端头", {})
                # 优先用"n芯"格式，其次用"n×m"格式提取芯数
                if core_match:
                    cores = int(core_match.group(1))
                elif ctrl_cable_core_match:
                    cores = sum(int(n) for n, m in ctrl_cable_core_match)
                else:
                    cores = None
                if cores:
                    for key, code in cable_map.items():
                        if "≤" in key:
                            max_val = int(re.search(r'(\d+)', key).group(1))
                            if cores <= max_val:
                                quota = self.quota_by_code.get(code)
                                if quota:
                                    return {"code": quota["code"], "name": quota["name"], "unit": quota["unit"], "confidence": "high", "note": f"精确匹配（控制电缆终端头{cores}芯）", "need_confirm": False}
            else:
                # 电力电缆终端头 - 支持"n×m"格式，按**最大单芯截面**计算
                cable_map = self.MATERIAL_QUOTA_MAP.get("电力电缆终端头", {})
                if power_cable_match:
                    # "4×25+1×16" → max(25,16)=25mm²（按最大单芯）
                    section = max(int(m) for n, m in power_cable_match)
                else:
                    section_match2 = re.search(r'[≤\s]*(\d+)\s*mm', item_lower, re.IGNORECASE)
                    actual_section = section_match2 if section_match2 else section_match
                    section = int(actual_section.group(1)) if actual_section else None
                if section:
                    for key, code in cable_map.items():
                        if "≤" in key:
                            max_val = int(re.search(r'(\d+)', key).group(1))
                            if section <= max_val:
                                quota = self.quota_by_code.get(code)
                                if quota:
                                    return {"code": quota["code"], "name": quota["name"], "unit": quota["unit"], "confidence": "high", "note": f"精确匹配（电力电缆终端头，最大单芯{str(section)}mm²）", "need_confirm": False}
        elif "控制电缆" in item_lower:
            # ★ 控制电缆选用规则：按芯数选择定额编号
            cable_map = self.MATERIAL_QUOTA_MAP.get("控制电缆", {})
            # 优先用"n芯"格式，其次用"n×m"格式提取芯数
            if core_match:
                cores = int(core_match.group(1))
            elif ctrl_cable_core_match:
                # 从"10×1.5"等格式提取芯数之和
                cores = sum(int(n) for n, m in ctrl_cable_core_match)
            else:
                cores = None
            if cores:
                for key, code in cable_map.items():
                    if "≤" in key:
                        max_val = int(re.search(r'(\d+)', key).group(1))
                        if cores <= max_val:
                            quota = self.quota_by_code.get(code)
                            if quota:
                                return {"code": quota["code"], "name": quota["name"], "unit": quota["unit"], "confidence": "high", "note": f"精确匹配（控制电缆{cores}芯）", "need_confirm": False}
        elif "电力电缆" in item_lower or "电力电缆敷设" in item_lower or \
             re.search(r'(wdz-?yjz?|yjv|yv|vv|yv22|yv32|vv22|vv32)[-_\d]*\d+[×x]\d+', item_lower):
            # ★ 电力电缆选用规则（综合解释第四册）：
            #   定额按三芯编制，五芯×1.15、六芯×1.3、每增一芯+15%
            #   电力电缆按"最大单芯截面"选择定额编号
            cable_map = self.MATERIAL_QUOTA_MAP.get("电力电缆", {})
            # 计算**最大单芯截面**：4×25+1×16 → max(25,16)=25mm²（按最大单芯套定额）
            if power_cable_match:
                # 取所有芯中的最大截面
                section = max(int(m) for n, m in power_cable_match)
                for key, code in cable_map.items():
                    if "≤" in key and "kV" not in key:
                        max_val = int(re.search(r'(\d+)', key).group(1))
                        if section <= max_val:
                            quota = self.quota_by_code.get(code)
                            if quota:
                                return {"code": quota["code"], "name": quota["name"], "unit": quota["unit"], "confidence": "high", "note": f"精确匹配（电力电缆最大单芯{str(section)}mm²）", "need_confirm": False}
            # 其次用"截面≤XX"格式
            elif section_match:
                section = int(section_match.group(1))
                for key, code in cable_map.items():
                    if "≤" in key and "kV" not in key:
                        max_val = int(re.search(r'(\d+)', key).group(1))
                        if section <= max_val:
                            quota = self.quota_by_code.get(code)
                            if quota:
                                return {"code": quota["code"], "name": quota["name"], "unit": quota["unit"], "confidence": "high", "note": f"精确匹配（电力电缆）", "need_confirm": False}
            elif "10kV" in item_upper and "3×300" in item_upper:
                quota = self.quota_by_code.get("4-9-166")
                if quota:
                    return {"code": quota["code"], "name": quota["name"], "unit": quota["unit"], "confidence": "high", "note": "精确匹配（10kV电力电缆3×300）", "need_confirm": False}
        elif "直埋电缆" in item_lower:
            quota = self.quota_by_code.get("4-9-127")
            if quota:
                return {"code": quota["code"], "name": quota["name"], "unit": quota["unit"], "confidence": "high", "note": "精确匹配（直埋电缆）", "need_confirm": False}

        # ============================================
        # 电动机功率匹配 (kW)
        # ============================================
        if "电动机" in item_lower or ("电机" in item_lower and "检查接线" in item_lower):
            power_match = re.search(r'(\d+(?:\.\d+)?)\s*kW', item_lower, re.IGNORECASE)
            if power_match:
                power = float(power_match.group(1))
                is_explosion = "防爆" in item_lower
                motor_map = self.MATERIAL_QUOTA_MAP.get("防爆电动机" if is_explosion else "异步电动机", {})
                for key, code in motor_map.items():
                    if "≤" in key:
                        max_val = float(re.search(r'[\d\.]+', key).group())
                        if power <= max_val:
                            quota = self.quota_by_code.get(code)
                            if quota:
                                return {"code": quota["code"], "name": quota["name"], "unit": quota["unit"], "confidence": "high", "note": f"精确匹配（{'防爆' if is_explosion else ''}电动机）", "need_confirm": False}

        # ============================================
        # 变频电机调试匹配
        # ============================================
        if "变频" in item_lower and "调试" in item_lower:
            power_match = re.search(r'(\d+(?:\.\d+)?)\s*kW', item_lower, re.IGNORECASE)
            if power_match:
                power = float(power_match.group(1))
                is_high_voltage = "高压" in item_lower or "10kV" in item_lower.upper()
                motor_map = self.MATERIAL_QUOTA_MAP.get("变频电机调试", {})
                for key, code in motor_map.items():
                    if "高压" in key and is_high_voltage:
                        quota = self.quota_by_code.get(code)
                        if quota:
                            return {"code": quota["code"], "name": quota["name"], "unit": quota["unit"], "confidence": "high", "note": "精确匹配（高压变频电机调试）", "need_confirm": False}
                    elif "≤" in key:
                        max_val = float(re.search(r'[\d\.]+', key).group())
                        if power <= max_val:
                            quota = self.quota_by_code.get(code)
                            if quota:
                                return {"code": quota["code"], "name": quota["name"], "unit": quota["unit"], "confidence": "high", "note": "精确匹配（变频电机调试）", "need_confirm": False}

        # ============================================
        # 配电箱/柜半周长匹配
        # ============================================
        if any(kw in item_lower for kw in ["配电箱", "控制箱", "动力箱", "开关箱"]):
            size_match = re.search(r'半周长\s*[≤\s]*(\d+(?:\.\d+)?)\s*m', item_lower, re.IGNORECASE)
            if size_match:
                size = float(size_match.group(1))
                box_map = self.MATERIAL_QUOTA_MAP.get("配电箱", {})
                for key, code in box_map.items():
                    if "≤" in key:
                        max_val = float(re.search(r'[\d\.]+', key).group())
                        if size <= max_val:
                            quota = self.quota_by_code.get(code)
                            if quota:
                                return {"code": quota["code"], "name": quota["name"], "unit": quota["unit"], "confidence": "high", "note": f"精确匹配（配电箱≤{max_val}m）", "need_confirm": False}
            elif "落地" in item_lower:
                quota = self.quota_by_code.get("4-2-74")
                if quota:
                    return {"code": quota["code"], "name": quota["name"], "unit": quota["unit"], "confidence": "high", "note": "精确匹配（落地式配电箱）", "need_confirm": False}
        elif "配电柜" in item_lower or "高压配电柜" in item_lower:
            quota = self.quota_by_code.get("4-2-72")
            if quota:
                return {"code": quota["code"], "name": quota["name"], "unit": quota["unit"], "confidence": "high", "note": "精确匹配（低压配电柜）", "need_confirm": False}

        # ============================================
        # UPS功率匹配
        # ============================================
        if "UPS" in item_upper or "不间断电源" in item_lower:
            kva_match = re.search(r'(\d+(?:\.\d+)?)\s*kV·?A', item_lower, re.IGNORECASE)
            if kva_match:
                kva = float(kva_match.group(1))
                is_three_phase = "三相" in item_lower
                ups_map = self.MATERIAL_QUOTA_MAP.get("UPS电源", {})
                for key, code in ups_map.items():
                    if "三相" in key and is_three_phase:
                        max_val = float(re.search(r'(\d+)', key).group())
                        if kva <= max_val:
                            quota = self.quota_by_code.get(code)
                            if quota:
                                return {"code": quota["code"], "name": quota["name"], "unit": quota["unit"], "confidence": "high", "note": "精确匹配（三相UPS）", "need_confirm": False}
                    elif "单相" in key and not is_three_phase:
                        max_val = float(re.search(r'(\d+)', key).group())
                        if kva <= max_val:
                            quota = self.quota_by_code.get(code)
                            if quota:
                                return {"code": quota["code"], "name": quota["name"], "unit": quota["unit"], "confidence": "high", "note": "精确匹配（单相UPS）", "need_confirm": False}

        # ============================================
        # 蓄电池容量匹配
        # ============================================
        if "蓄电池" in item_lower:
            ah_match = re.search(r'(\d+(?:\.\d+)?)\s*[AA]h?', item_lower, re.IGNORECASE)
            battery_map = self.MATERIAL_QUOTA_MAP.get("蓄电池", {})
            if ah_match:
                ah = float(ah_match.group(1))
                for key, code in battery_map.items():
                    if "≤" in key:
                        max_val = float(re.search(r'[\d\.]+', key).group())
                        if ah <= max_val:
                            quota = self.quota_by_code.get(code)
                            if quota:
                                return {"code": quota["code"], "name": quota["name"], "unit": quota["unit"], "confidence": "high", "note": f"精确匹配（蓄电池{ah}Ah）", "need_confirm": False}
            elif "免维护" in item_lower:
                if "100Ah" in item_lower or "100AH" in item_upper:
                    quota = self.quota_by_code.get("4-5-26")
                    if quota:
                        return {"code": quota["code"], "name": quota["name"], "unit": quota["unit"], "confidence": "high", "note": "精确匹配（免维护100Ah蓄电池）", "need_confirm": False}
                elif "200Ah" in item_lower or "200AH" in item_upper:
                    quota = self.quota_by_code.get("4-5-27")
                    if quota:
                        return {"code": quota["code"], "name": quota["name"], "unit": quota["unit"], "confidence": "high", "note": "精确匹配（免维护200Ah蓄电池）", "need_confirm": False}
                elif "300Ah" in item_lower or "300AH" in item_upper:
                    quota = self.quota_by_code.get("4-5-28")
                    if quota:
                        return {"code": quota["code"], "name": quota["name"], "unit": quota["unit"], "confidence": "high", "note": "精确匹配（免维护300Ah蓄电池）", "need_confirm": False}

        # ============================================
        # 调试类匹配
        # ============================================
        if "调试" in item_lower:
            # 报警系统调试
            point_match = re.search(r'(\d+)\s*点', item_lower)
            if point_match:
                points = int(point_match.group(1))
                if points <= 64:
                    code = "9-5-1"
                elif points <= 256:
                    code = "9-5-3"
                else:
                    code = None
                if code:
                    quota = self.quota_by_code.get(code)
                    if quota:
                        return {"code": quota["code"], "name": quota["name"], "unit": quota["unit"], "confidence": "high", "note": f"精确匹配（报警系统调试{points}点）", "need_confirm": False}
            # 电机调试
            if "电机" in item_lower:
                power_match = re.search(r'(\d+(?:\.\d+)?)\s*kW', item_lower, re.IGNORECASE)
                if power_match:
                    power = float(power_match.group(1))
                    debug_map = self.MATERIAL_QUOTA_MAP.get("电机调试", {})
                    for key, code in debug_map.items():
                        if "≤" in key:
                            max_val = float(re.search(r'[\d\.]+', key).group())
                            if power <= max_val:
                                quota = self.quota_by_code.get(code)
                                if quota:
                                    return {"code": quota["code"], "name": quota["name"], "unit": quota["unit"], "confidence": "high", "note": "精确匹配（电机负载调试）", "need_confirm": False}

        # ============================================
        # 母线槽/桥架尺寸匹配
        # ============================================
        if "母线槽" in item_lower:
            a_match = re.search(r'(\d+)\s*A', item_lower)
            if a_match:
                amp = int(a_match.group(1))
                bus_map = self.MATERIAL_QUOTA_MAP.get("母线槽", {})
                for key, code in bus_map.items():
                    if "≤" in key:
                        max_val = int(re.search(r'(\d+)', key).group())
                        if amp <= max_val:
                            quota = self.quota_by_code.get(code)
                            if quota:
                                return {"code": quota["code"], "name": quota["name"], "unit": quota["unit"], "confidence": "high", "note": f"精确匹配（母线槽{amp}A）", "need_confirm": False}
            if "始端箱" in item_lower:
                quota = self.quota_by_code.get("4-3-122")
                if quota:
                    return {"code": quota["code"], "name": quota["name"], "unit": quota["unit"], "confidence": "high", "note": "精确匹配（母线槽始端箱）", "need_confirm": False}
        elif any(kw in item_lower for kw in ["梯式桥架", "梯架安装"]):
            mm_match = re.search(r'[≤\s]*(\d+)\s*mm', item_lower)
            if mm_match:
                mm = int(mm_match.group(1))
                tray_map = self.MATERIAL_QUOTA_MAP.get("梯式桥架", {})
                for key, code in tray_map.items():
                    if "≤" in key:
                        max_val = int(re.search(r'(\d+)', key).group())
                        if mm <= max_val:
                            quota = self.quota_by_code.get(code)
                            if quota:
                                return {"code": quota["code"], "name": quota["name"], "unit": quota["unit"], "confidence": "high", "note": f"精确匹配（梯式桥架{mm}mm）", "need_confirm": False}
        elif any(kw in item_lower for kw in ["槽式桥架", "槽架安装", "桥架安装"]):
            mm_match = re.search(r'[≤\s]*(\d+)\s*mm', item_lower)
            if mm_match:
                mm = int(mm_match.group(1))
                tray_map = self.MATERIAL_QUOTA_MAP.get("槽式桥架", {})
                for key, code in tray_map.items():
                    if "≤" in key:
                        max_val = int(re.search(r'(\d+)', key).group())
                        if mm <= max_val:
                            quota = self.quota_by_code.get(code)
                            if quota:
                                return {"code": quota["code"], "name": quota["name"], "unit": quota["unit"], "confidence": "high", "note": f"精确匹配（槽式桥架{mm}mm）", "need_confirm": False}
            else:
                # 默认桥架
                quota = self.quota_by_code.get("4-9-65")
                if quota:
                    return {"code": quota["code"], "name": quota["name"], "unit": quota["unit"], "confidence": "high", "note": "精确匹配（电缆桥架）", "need_confirm": False}

        # ============================================
        # 路灯杆高度匹配
        # ============================================
        if "路灯" in item_lower and "杆" in item_lower:
            m_match = re.search(r'杆长\s*[≤\s]*(\d+(?:\.\d+)?)\s*m', item_lower)
            if m_match:
                m = float(m_match.group(1))
                pole_map = self.MATERIAL_QUOTA_MAP.get("路灯杆", {})
                for key, code in pole_map.items():
                    if "≤" in key:
                        max_val = float(re.search(r'[\d\.]+', key).group())
                        if m <= max_val:
                            quota = self.quota_by_code.get(code)
                            if quota:
                                return {"code": quota["code"], "name": quota["name"], "unit": quota["unit"], "confidence": "high", "note": f"精确匹配（路灯杆≤{max_val}m）", "need_confirm": False}

        # ============================================
        # 接线盒/穿线盒/挠性管
        # ============================================
        if "穿线盒" in item_lower and "防爆" in item_lower:
            quota = self.quota_by_code.get("6-8-97")
            if quota:
                return {"code": quota["code"], "name": quota["name"], "unit": quota["unit"], "confidence": "high", "note": "精确匹配（防爆穿线盒）", "need_confirm": False}
        elif "挠性管" in item_lower:
            if "防爆" in item_lower:
                quota = self.quota_by_code.get("6-8-99")
            else:
                quota = self.quota_by_code.get("6-8-98")
            if quota:
                return {"code": quota["code"], "name": quota["name"], "unit": quota["unit"], "confidence": "high", "note": f"精确匹配（{'防爆' if '防爆' in item_lower else ''}挠性管）", "need_confirm": False}
        elif "防爆胶泥" in item_lower:
            quota = self.quota_by_code.get("6-8-102")
            if quota:
                return {"code": quota["code"], "name": quota["name"], "unit": quota["unit"], "confidence": "high", "note": "精确匹配（防爆胶泥）", "need_confirm": False}
        elif "金属软管" in item_lower:
            quota = self.quota_by_code.get("4-12-173")
            if quota:
                return {"code": quota["code"], "name": quota["name"], "unit": quota["unit"], "confidence": "high", "note": "精确匹配（金属软管敷设）", "need_confirm": False}
        elif "监控立柱" in item_lower:
            quota = self.quota_by_code.get("3-6-60")
            if quota:
                return {"code": quota["code"], "name": quota["name"], "unit": quota["unit"], "confidence": "high", "note": "精确匹配（监控立柱安装）", "need_confirm": False}
        elif "接线盒" in item_lower or "开关盒" in item_lower or "插座盒" in item_lower:
            if "防爆" in item_lower:
                quota = self.quota_by_code.get("4-13-181")
            elif "明装" in item_lower:
                quota = self.quota_by_code.get("4-13-180")
            else:
                quota = self.quota_by_code.get("4-13-179")
            if quota:
                return {"code": quota["code"], "name": quota["name"], "unit": quota["unit"], "confidence": "high", "note": "精确匹配（接线盒）", "need_confirm": False}

        # ============================================
        # 插排/插座匹配
        # ============================================
        if "插排" in item_lower or "插座" in item_lower or "排插" in item_lower:
            socket_map = {
                ("防爆", "三相", "≤15A"): "4-14-409",
                ("防爆", "三相", "≤60A"): "4-14-410",
                ("防爆", "单相带接地", "≤15A"): "4-14-407",
                ("防爆", "单相带接地", "≤60A"): "4-14-408",
                ("防爆", "单相", "≤15A"): "4-14-405",
                ("防爆", "单相", "≤60A"): "4-14-406",
                ("防爆",): "4-14-405",
                ("三相带接地", "≤15A"): "4-14-403",
                ("三相带接地", "≤30A"): "4-14-404",
                ("三相", "≤15A"): "4-14-397",
                ("三相", "≤30A"): "4-14-398",
                ("单相带接地", "≤15A"): "4-14-395",
                ("单相带接地", "≤30A"): "4-14-396",
                ("单相", "≤15A"): "4-14-393",
                ("单相", "≤30A"): "4-14-394",
                ("暗装",): "4-14-399",
                ("明装",): "4-14-393",
            }
            is_explosion = "防爆" in item_lower
            is_three_phase = "三相" in item_lower
            is_ground = "带接地" in item_lower or "接地" in item_lower
            is_hidden = "暗装" in item_lower
            is_explicit_current = any(x in item_lower for x in ["15A", "30A", "≤15", "≤30", "60A"])
            current_15 = any(x in item_lower for x in ["15A", "≤15A", "≤15"])
            current_30 = any(x in item_lower for x in ["30A", "≤30A", "≤30", "60A"])

            # 优先按 防爆→三相/单相→电流 顺序匹配
            if is_explosion:
                if is_three_phase:
                    code = socket_map.get(("防爆", "三相", "≤15A")) if not current_30 else socket_map.get(("防爆", "三相", "≤60A"))
                else:
                    if is_ground:
                        code = socket_map.get(("防爆", "单相带接地", "≤15A")) if not current_30 else socket_map.get(("防爆", "单相带接地", "≤60A"))
                    else:
                        code = socket_map.get(("防爆", "单相", "≤15A")) if not current_30 else socket_map.get(("防爆", "单相", "≤60A"))
                if code:
                    quota = self.quota_by_code.get(code)
                    if quota:
                        return {"code": quota["code"], "name": quota["name"], "unit": quota["unit"], "confidence": "high", "note": "精确匹配（防爆插座）", "need_confirm": False}
            elif is_three_phase:
                if is_ground:
                    code = socket_map.get(("三相带接地", "≤15A")) if not current_30 else socket_map.get(("三相带接地", "≤30A"))
                else:
                    code = socket_map.get(("三相", "≤15A")) if not current_30 else socket_map.get(("三相", "≤30A"))
                if code:
                    quota = self.quota_by_code.get(code)
                    if quota:
                        return {"code": quota["code"], "name": quota["name"], "unit": quota["unit"], "confidence": "high", "note": "精确匹配（插座）", "need_confirm": False}
            elif is_hidden:
                quota = self.quota_by_code.get("4-14-399")
                if quota:
                    return {"code": quota["code"], "name": quota["name"], "unit": quota["unit"], "confidence": "high", "note": "精确匹配（暗装插座）", "need_confirm": False}
            else:
                # 默认普通单相明装≤15A
                quota = self.quota_by_code.get("4-14-393")
                if quota:
                    return {"code": quota["code"], "name": quota["name"], "unit": quota["unit"], "confidence": "high", "note": "精确匹配（插座）", "need_confirm": False}

        # ============================================
        # 摄像机类型匹配
        # ============================================
        if "摄像机" in item_lower or "摄像头" in item_lower:
            if "防爆" in item_lower:
                quota = self.quota_by_code.get("5-6-82")
                if quota:
                    return {"code": quota["code"], "name": quota["name"], "unit": quota["unit"], "confidence": "high", "note": "精确匹配（防爆摄像机）", "need_confirm": False}
            elif "枪机" in item_lower:
                quota = self.quota_by_code.get("5-6-83")
                if quota:
                    return {"code": quota["code"], "name": quota["name"], "unit": quota["unit"], "confidence": "high", "note": "精确匹配（枪机）", "need_confirm": False}
            elif "球机" in item_lower or "球型" in item_lower:
                quota = self.quota_by_code.get("5-6-80")
                if quota:
                    return {"code": quota["code"], "name": quota["name"], "unit": quota["unit"], "confidence": "high", "note": "精确匹配（球型摄像机）", "need_confirm": False}
            elif "半球" in item_lower:
                quota = self.quota_by_code.get("5-6-79")
                if quota:
                    return {"code": quota["code"], "name": quota["name"], "unit": quota["unit"], "confidence": "high", "note": "精确匹配（半球摄像机）", "need_confirm": False}
            elif "云台" in item_lower:
                quota = self.quota_by_code.get("5-6-84")
                if quota:
                    return {"code": quota["code"], "name": quota["name"], "unit": quota["unit"], "confidence": "high", "note": "精确匹配（云台摄像机）", "need_confirm": False}
            else:
                quota = self.quota_by_code.get("5-6-78")
                if quota:
                    return {"code": quota["code"], "name": quota["name"], "unit": quota["unit"], "confidence": "high", "note": "精确匹配（监控摄像机）", "need_confirm": False}

        # ============================================
        # 视频监控调试
        # ============================================
        if "视频监控调试" in item_lower or "监控系统调试" in item_lower:
            ch_match = re.search(r'(\d+)\s*路', item_lower)
            if ch_match:
                channels = int(ch_match.group(1))
                if channels <= 4:
                    quota = self.quota_by_code.get("6-5-50")
                elif channels <= 9:
                    quota = self.quota_by_code.get("6-5-51")
                elif channels <= 16:
                    quota = self.quota_by_code.get("6-5-52")
                else:
                    quota = None
                if quota:
                    return {"code": quota["code"], "name": quota["name"], "unit": quota["unit"], "confidence": "high", "note": f"精确匹配（视频监控调试{channels}路）", "need_confirm": False}

        # ============================================
        # 交换机/网络设备
        # ============================================
        if "交换机" in item_lower:
            if "≤24口" in item_lower or "24口" in item_lower or "小于等于24" in item_lower:
                quota = self.quota_by_code.get("5-1-86")
                if quota:
                    return {"code": quota["code"], "name": quota["name"], "unit": quota["unit"], "confidence": "high", "note": "精确匹配（交换机≤24口）", "need_confirm": False}
            elif "插槽" in item_lower:
                quota = self.quota_by_code.get("5-1-89")
                if quota:
                    return {"code": quota["code"], "name": quota["name"], "unit": quota["unit"], "confidence": "high", "note": "精确匹配（插槽式交换机）", "need_confirm": False}

        # ============================================
        # 机柜
        # ============================================
        if "机柜" in item_lower or "机架" in item_lower:
            if "落地" in item_lower:
                quota = self.quota_by_code.get("5-2-20")
            elif "墙挂" in item_lower or "壁挂" in item_lower:
                quota = self.quota_by_code.get("5-2-21")
            else:
                quota = self.quota_by_code.get("5-2-20")
            if quota:
                return {"code": quota["code"], "name": quota["name"], "unit": quota["unit"], "confidence": "high", "note": "精确匹配（机柜）", "need_confirm": False}

        # ============================================
        # 光缆/光纤
        # ============================================
        if "光缆" in item_lower and "终端盒" in item_lower:
            if "≤12芯" in item_lower or "12芯" in item_lower:
                quota = self.quota_by_code.get("5-2-96")
            elif "≤24芯" in item_lower or "24芯" in item_lower:
                quota = self.quota_by_code.get("5-2-97")
            else:
                quota = self.quota_by_code.get("5-2-97")
            if quota:
                return {"code": quota["code"], "name": quota["name"], "unit": quota["unit"], "confidence": "high", "note": "精确匹配（光缆终端盒）", "need_confirm": False}
        elif "光缆" in item_lower:
            quota = self.quota_by_code.get("5-2-45")
            if quota:
                return {"code": quota["code"], "name": quota["name"], "unit": quota["unit"], "confidence": "high", "note": "精确匹配（光缆）", "need_confirm": False}
        elif "光纤熔接" in item_lower or "熔接法" in item_lower:
            quota = self.quota_by_code.get("5-2-92")
            if quota:
                return {"code": quota["code"], "name": quota["name"], "unit": quota["unit"], "confidence": "high", "note": "精确匹配（光纤熔接）", "need_confirm": False}
        elif "尾纤" in item_lower:
            quota = self.quota_by_code.get("5-2-102")
            if quota:
                return {"code": quota["code"], "name": quota["name"], "unit": quota["unit"], "confidence": "high", "note": "精确匹配（尾纤）", "need_confirm": False}
        elif "光纤跳线" in item_lower:
            quota = self.quota_by_code.get("5-2-60")
            if quota:
                return {"code": quota["code"], "name": quota["name"], "unit": quota["unit"], "confidence": "high", "note": "精确匹配（光纤跳线）", "need_confirm": False}
        elif "光纤测试" in item_lower or "光缆测试" in item_lower or "光纤链路" in item_lower:
            quota = self.quota_by_code.get("5-2-108")
            if quota:
                return {"code": quota["code"], "name": quota["name"], "unit": quota["unit"], "confidence": "high", "note": "精确匹配（光纤测试）", "need_confirm": False}

        # ============================================
        # 双绞线/网线
        # ============================================
        if "双绞线" in item_lower or "网线" in item_lower or "超五类" in item_lower:
            if "测试" in item_lower:
                quota = self.quota_by_code.get("5-2-107")
            else:
                quota = self.quota_by_code.get("5-2-42")
            if quota:
                return {"code": quota["code"], "name": quota["name"], "unit": quota["unit"], "confidence": "high", "note": "精确匹配（双绞线/网线）", "need_confirm": False}

        # ============================================
        # 信息插座
        # ============================================
        if "信息插座" in item_lower or "插座" in item_lower:
            if "双口" in item_lower:
                quota = self.quota_by_code.get("5-2-85")
            else:
                quota = self.quota_by_code.get("5-2-84")
            if quota:
                return {"code": quota["code"], "name": quota["name"], "unit": quota["unit"], "confidence": "high", "note": "精确匹配（信息插座）", "need_confirm": False}

        # ============================================
        # 光电转换器
        # ============================================
        if "光电转换器" in item_lower:
            quota = self.quota_by_code.get("11-9-65")
            if quota:
                return {"code": quota["code"], "name": quota["name"], "unit": quota["unit"], "confidence": "high", "note": "精确匹配（光电转换器）", "need_confirm": False}

        # ============================================
        # 接地跨接线/等电位连接
        # ============================================
        if "等电位连接" in item_lower or "接地跨接线" in item_lower or "黄绿双色线" in item_lower:
            quota = self.quota_by_code.get("5-7-65")
            if quota:
                return {"code": quota["code"], "name": quota["name"], "unit": quota["unit"], "confidence": "high", "note": "精确匹配（等电位连接/接地跨接）", "need_confirm": False}
        elif "接地跨接" in item_lower and "构架" in item_lower:
            quota = self.quota_by_code.get("4-10-60")
            if quota:
                return {"code": quota["code"], "name": quota["name"], "unit": quota["unit"], "confidence": "high", "note": "精确匹配（构架接地跨接）", "need_confirm": False}

        # ============================================
        # 铁构件/金属结构
        # ============================================
        if any(kw in item_lower for kw in ["铁构件", "金属结构件"]) and "制作" in item_lower:
            quota = self.quota_by_code.get("4-7-5")
            if quota:
                return {"code": quota["code"], "name": quota["name"], "unit": quota["unit"], "confidence": "high", "note": "精确匹配（铁构件制作）", "need_confirm": False}
        elif any(kw in item_lower for kw in ["铁构件", "金属结构件"]) and "安装" in item_lower:
            quota = self.quota_by_code.get("4-7-6")
            if quota:
                return {"code": quota["code"], "name": quota["name"], "unit": quota["unit"], "confidence": "high", "note": "精确匹配（铁构件安装）", "need_confirm": False}
        elif "基础槽钢" in item_lower:
            quota = self.quota_by_code.get("4-7-1")
            if quota:
                return {"code": quota["code"], "name": quota["name"], "unit": quota["unit"], "confidence": "high", "note": "精确匹配（基础槽钢）", "need_confirm": False}
        elif any(kw in item_lower for kw in ["槽钢", "角钢", "扁钢", "方管", "钢板"]) and ("制作" in item_lower or "安装" in item_lower):
            # 监控立柱等金属结构
            quota = self.quota_by_code.get("4-7-6")
            if quota:
                return {"code": quota["code"], "name": quota["name"], "unit": quota["unit"], "confidence": "high", "note": "精确匹配（金属结构件）", "need_confirm": False}

        # ============================================
        # 通用 MATERIAL_QUOTA_MAP 查找（仅限简单字符串映射，排除规格化dict映射）
        # ============================================
        for mat_name, code_or_map in self.MATERIAL_QUOTA_MAP.items():
            if isinstance(code_or_map, dict):
                continue  # 跳过规格化映射，由专门的elif处理
            if mat_name.lower() in item_lower:
                quota = self.quota_by_code.get(code_or_map)
                if quota:
                    return {"code": quota["code"], "name": quota["name"], "unit": quota["unit"], "confidence": "high", "note": f"精确匹配（{mat_name}）", "need_confirm": False}

        return None

    def _fuzzy_match(self, item_name: str, unit: str = None) -> Optional[Dict]:
        """模糊匹配（基于关键词索引）"""
        keywords = self._extract_keywords(item_name)

        candidates = []
        for kw in keywords:
            if kw in self.quota_by_keyword:
                candidates.extend(self.quota_by_keyword[kw])

        if not candidates:
            return None

        # 去重并排序
        seen = set()
        unique_candidates = []
        for c in candidates:
            if c["code"] not in seen:
                seen.add(c["code"])
                unique_candidates.append(c)

        return {
            "code": unique_candidates[0]["code"],
            "name": unique_candidates[0]["name"],
            "unit": unique_candidates[0]["unit"],
            "confidence": "medium",
            "note": "模糊匹配，建议核对",
            "need_confirm": True
        }

    def _web_search_match(self, item_name: str, candidates: List[Dict]) -> Optional[Dict]:
        """联网搜索增强匹配"""
        try:
            import requests

            search_data = {
                "model": "MiniMax-Search",
                "query": f"{item_name} 河南省2016安装定额 套定额",
                "search_result_return_length": 3
            }

            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }

            response = requests.post(
                self.search_api_url,
                headers=headers,
                json=search_data,
                timeout=30
            )

            if response.status_code != 200:
                return None

            result = response.json()
            if "data" not in result or not result["data"]:
                return None

            # 从搜索结果中提取关键词，找更精确的匹配
            search_text = ""
            for item in result["data"][:3]:
                text = item.get("text", "")
                search_text += text + "\n"

            # 尝试在候选定额中找到更匹配的
            best_match = None
            best_score = 0

            for q in candidates:
                name_lower = q["name"].lower()
                score = 0

                # 计算搜索结果与定额名称的匹配度
                for kw in self._extract_keywords(item_name):
                    if kw in name_lower:
                        score += 2
                    if kw in search_text.lower():
                        score += 1

                # 检查定额编号是否在搜索结果中提到
                if q["code"] in search_text:
                    score += 5

                if score > best_score:
                    best_score = score
                    best_match = q

            if best_match and best_score > 3:
                return {
                    "code": best_match["code"],
                    "name": best_match["name"],
                    "unit": best_match["unit"],
                    "confidence": "medium",
                    "note": "联网搜索增强匹配，建议核对",
                    "need_confirm": True
                }

        except Exception:
            pass

        return None

    def batch_match(self, items: List[Dict], batch_size: int = 10) -> List[Dict]:
        """批量匹配"""
        results = []

        for i, item in enumerate(items):
            print(f"正在匹配 [{i+1}/{len(items)}]: {item.get('name', '')[:30]}...")

            result = self.match(
                item_name=item.get("name", ""),
                quantity=item.get("quantity"),
                unit=item.get("unit")
            )

            result["original_name"] = item.get("name")
            result["original_quantity"] = item.get("quantity")
            result["original_unit"] = item.get("unit")

            results.append(result)

        return results

    def _find_relevant_quotas(self, item_name: str, unit: str = None) -> List[Dict]:
        """从定额库中查找相关定额"""
        keywords = self._extract_keywords(item_name)

        if not keywords:
            return []

        relevant = []
        item_lower = item_name.lower()

        for q in self.quota_data:
            name_lower = q["name"].lower()
            score = 0

            # 关键词匹配
            for kw in keywords:
                if len(kw) >= 2 and kw in name_lower:
                    score += 3

            # 数字规格匹配
            item_specs = set(re.findall(r'\d+', item_name))
            name_specs = set(re.findall(r'\d+', name_lower))
            common_specs = item_specs & name_specs
            score += len(common_specs) * 0.5

            # 关键工程字符匹配
            engineering_chars = ['表', '仪', '控', '阀', '管', '线', '电', '机', '泵', '箱', '柜', '缆', '杆', '架', '盒']
            for char in engineering_chars:
                if char in item_lower and char in name_lower:
                    score += 1

            if score > 0:
                relevant.append((q, score))

        relevant.sort(key=lambda x: x[1], reverse=True)
        return [q for q, score in relevant[:10]]

    def _extract_keywords(self, text: str) -> List[str]:
        """提取关键词"""
        stopwords = ["安装", "共计", "含", "等", "规格", "制作", "施工", "乙供材", "材料", "共计", "人工", "设备", "工程"]
        text_lower = text.lower()

        for sw in stopwords:
            text_lower = text_lower.replace(sw, "")

        # 按常见分隔符分割
        tokens = re.split(r'[\s,，、*×().。、]+', text_lower)
        words = [t.strip() for t in tokens if len(t.strip()) >= 2]

        # 提取特殊规格模式
        specs = re.findall(r'[a-zA-Z]+[-*]?\d+[\*]?\d*', text)  # DN25, YJV-4*2.5
        words.extend(specs)

        sizes = re.findall(r'\d+\.?\d*\*\d+[\*\d]*', text)  # 50*50*5
        words.extend(sizes)

        return list(set(words))

    def _check_unit_match(self, item_unit: str, quota_unit: str) -> float:
        """检查单位匹配度"""
        if not item_unit or not quota_unit:
            return 0

        item_unit = item_unit.lower().strip()
        quota_unit = quota_unit.lower().strip()

        if item_unit == quota_unit:
            return 2

        if item_unit in quota_unit or quota_unit in item_unit:
            return 1

        return 0


if __name__ == "__main__":
    print("LocalMatcher 已初始化（改进版）")
