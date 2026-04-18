# 工程量识别模块 - 待办任务清单

## 项目信息
- 工作目录: `D:\claude code`
- 项目路径: `D:\claude code\skills\quota-matcher\`
- 唤醒词: "继续套定额项目"

## 任务清单

### Task 1: 创建 quantity_extractor.py 基础框架 ⬜
- [ ] 创建测试文件 `tests/test_quantity_extractor.py`
- [ ] 实现 `QuantityExtractor`、`StructuredTableExtractor`、`DescriptiveExtractor` 三个主类
- [ ] 基础框架测试通过

### Task 2: 扩展规则模式库 ⬜
- [ ] 添加更多正则表达式模式（接线盒、活接头、钢板等）
- [ ] 测试验证新模式

### Task 3: 集成AI语义解析（兜底） ⬜
- [ ] 添加 `AISemanticParser` 类
- [ ] 在 `DescriptiveExtractor` 中集成AI调用作为规则兜底

### Task 4: 集成到quota_matcher.py主流程 ⬜
- [ ] 在 `QuotaMatcher.__init__` 中初始化 `QuantityExtractor`
- [ ] 在 `process()` 方法中调用工程量识别

### Task 5: 输出字段增强验证 ⬜
- [ ] 验证增强字段（spec, source, confidence, extraction_note）正确输出
- [ ] 完整流程测试

## 设计文档
- 设计: `skills/quota-matcher/docs/superpowers/specs/2026-04-18-quantity-extractor-design.md`
- 计划: `skills/quota-matcher/docs/superpowers/plans/2026-04-18-quantity-extractor-implementation.md`

## 快速启动
```bash
cd /d/claude code
# 激活环境后执行 Task 1
python -m pytest skills/quota-matcher/tests/test_quantity_extractor.py -v
```

## 核心设计
1. 有附表 → `StructuredTableExtractor` 精确提取（source=table, confidence=high）
2. 无附表 → `DescriptiveExtractor` 规则优先匹配（source=rule, confidence=high/medium）
3. 规则无法 → `AISemanticParser` AI兜底（source=ai, confidence=medium）
4. 无法解析 → 标记 low confidence 待人工确认（source=unparsed）
