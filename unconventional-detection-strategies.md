# C++ 耦合性检测 — 非常规检测方法实现策略

> 生成日期: 2026-06-11
> 负责成员: Creative Disruptor (方法设计 + 实现策略)
> 版本: v1.0 Final

---

## 概述

本文档详细描述 6 种非常规的耦合性检测方法，每种方法都包含：原理说明、实现伪代码、适用场景、与传统方法的对比优势。

这些方法的核心理念：**不是更精确地数依赖箭头，而是从多个角度交叉验证耦合度的真实性。**

---

## 方法 1: "自包含性爆破测试" (Self-Containment Blaster)

### 原理

传统方法正向分析 include 关系。这个方法**反向爆破** — 测试每个头文件能不能独立编译。能独立编译 = 无外部隐式依赖。

### 为什么"非常规"

- 传统工具回答："这个头文件依赖谁？"
- 这个方法回答："如果只 include 这个头文件，能不能编译通过？"

两种问题的答案可能不同 — 一个头文件可能在 include 链中"碰巧"能编译，但单独编译就失败。

### 适用场景

- 检测隐式依赖（宏、模板、前向声明缺失）
- 验证 include-what-you-use 的清理结果
- 作为重构后的回归测试

### 实现伪代码

```python
class SelfContainmentBlaster:
    """
    对每个头文件生成临时 .cpp：
    #include "target_header.h"
    int main() { return 0; }
    
    用该头文件所在 target 的编译标志编译它。
    编译失败 → 该头文件有隐式依赖。
    """
    
    def __init__(self, compile_database):
        self.db = compile_database
        self.results = {}
    
    def blast(self, header_path):
        # Step 1: 生成临时文件
        temp_cpp = tempfile.NamedTemporaryFile(
            suffix='.cpp', mode='w', delete=False
        )
        temp_cpp.write(f'#include "{header_path}"\n')
        temp_cpp.write('int main() { return 0; }\n')
        temp_cpp.close()
        
        try:
            # Step 2: 获取该头文件所在 target 的编译标志
            target = self.db.find_target_for_header(header_path)
            flags = self.db.get_compile_flags(target)
            
            # Step 3: 编译（只检查语法，不链接）
            result = subprocess.run(
                ['clang++', '-fsyntax-only', '-std=c++20'] + 
                flags + [temp_cpp.name],
                capture_output=True, text=True
            )
            
            # Step 4: 分析结果
            if result.returncode == 0:
                return SelfContainmentResult(
                    header=header_path,
                    is_self_contained=True,
                    missing_headers=[]
                )
            else:
                # 解析编译错误，提取"未声明的标识符"
                undeclared = self._parse_undeclared_identifiers(result.stderr)
                missing = []
                for type_name in undeclared:
                    defining_header = self._find_defining_header(type_name)
                    if defining_header:
                        missing.append(defining_header)
                
                return SelfContainmentResult(
                    header=header_path,
                    is_self_contained=False,
                    missing_headers=missing,
                    undeclared_types=undeclared
                )
        finally:
            os.unlink(temp_cpp.name)
    
    def blast_all(self, headers):
        """批量测试所有头文件"""
        results = []
        for header in headers:
            result = self.blast(header)
            results.append(result)
            self.results[header] = result
        return results
    
    def compute_self_containment_ratio(self):
        """计算自包含率"""
        total = len(self.results)
        contained = sum(1 for r in self.results.values() if r.is_self_contained)
        return contained / total if total > 0 else 0
    
    def _parse_undeclared_identifiers(self, stderr):
        """从 Clang 错误输出中提取未声明的标识符"""
        undeclared = []
        for line in stderr.split('\n'):
            # 匹配 "use of undeclared identifier 'XXX'"
            match = re.search(r"use of undeclared identifier '(\w+)'", line)
            if match:
                undeclared.append(match.group(1))
        return undeclared
    
    def _find_defining_header(self, type_name):
        """在编译数据库中查找类型定义所在的头文件"""
        # 遍历所有已知的头文件，用 Clang AST 查询
        for header in self.db.all_headers():
            result = subprocess.run(
                ['clang++', '-Xclang', '-ast-dump=json', 
                 '-fsyntax-only', '-std=c++20', header],
                capture_output=True, text=True
            )
            if type_name in result.stdout:
                return header
        return None
```

### 与传统方法的对比

| 维度 | 传统 include 分析 | 自包含性爆破 |
|------|-----------------|-------------|
| 检测范围 | 只检测 #include 关系 | 检测所有隐式依赖 |
| 准确性 | 可能遗漏隐式依赖 | 100% 准确（编译器验证） |
| 速度 | 快（图遍历） | 慢（需要编译） |
| 误报率 | 低 | 低 |
| 漏报率 | 中等 | 极低 |

---

## 方法 2: "编译时间 A/B 测试" (Compile Time A/B Test)

### 原理

通过实际测量编译时间来**验证**耦合检测结果的真实性。如果 BRI 说"这个头文件影响 50 个 TU"，我们通过 A/B 测试验证：修改这个头文件后，这 50 个 TU 的编译时间是否真的增加了。

### 为什么"非常规"

- 传统工具输出耦合度数字，但不验证数字的准确性
- 这个方法用**实验**验证理论计算

### 适用场景

- 验证 BRI 计算结果
- 识别"理论高耦合但实际影响低"的头文件（可能是编译器优化了）
- 为编译时间优化提供优先级排序

### 实现伪代码

```python
class CompileTimeABTest:
    """
    对比测试：
    A: 正常编译时间
    B: 修改头文件后的编译时间
    
    如果 B >> A，说明该头文件的 BRI 确实很高。
    """
    
    def __init__(self, build_system):
        self.build = build_system
    
    def ab_test_single(self, header, tu):
        """对单个 TU 做 A/B 测试"""
        # Phase A: 正常编译
        time_a = self._measure_compile_time(tu)
        
        # Phase B: 在 header 开头注入空行（触发重编译）
        original_content = self._read_file(header)
        modified_content = '\n' + original_content
        self._write_file(header, modified_content)
        
        # 重新编译该 TU
        time_b = self._measure_compile_time(tu)
        
        # 恢复文件
        self._write_file(header, original_content)
        
        return CompileTimeImpact(
            header=header,
            tu=tu,
            time_normal=time_a,
            time_after_change=time_b,
            impact_ratio=time_b / time_a if time_a > 0 else float('inf')
        )
    
    def ab_test_batch(self, header, dependent_tus):
        """对所有依赖该头文件的 TU 做批量 A/B 测试"""
        results = []
        for tu in dependent_tus:
            result = self.ab_test_single(header, tu)
            results.append(result)
        
        # 统计
        total_time_before = sum(r.time_normal for r in results)
        total_time_after = sum(r.time_after_change for r in results)
        
        return BatchCompileTimeImpact(
            header=header,
            individual_results=results,
            total_time_before=total_time_before,
            total_time_after=total_time_after,
            total_impact_ratio=total_time_after / total_time_before 
                if total_time_before > 0 else float('inf'),
            affected_tu_count=len(results)
        )
    
    def find_real_impact_headers(self, all_headers, all_tus):
        """找出真实影响最大的头文件"""
        impacts = []
        
        for header in all_headers:
            # 找依赖该头文件的 TU
            dependent_tus = self._find_dependent_tus(header, all_tus)
            if not dependent_tus:
                continue
            
            # 批量 A/B 测试
            batch_result = self.ab_test_batch(header, dependent_tus)
            impacts.append(batch_result)
        
        # 按真实影响排序
        return sorted(impacts, key=lambda x: x.total_impact_ratio, reverse=True)
    
    def _measure_compile_time(self, tu):
        """精确测量单个 TU 的编译时间"""
        start = time.perf_counter()
        subprocess.run(
            ['clang++', '-c', '-std=c++20', tu, '-o', '/dev/null'],
            capture_output=True
        )
        return time.perf_counter() - start
```

### 与传统方法的对比

| 维度 | BRI 理论计算 | 编译时间 A/B |
|------|-------------|-------------|
| 准确性 | 可能有偏差 | 实验验证，最准确 |
| 速度 | 快 | 慢（需要实际编译） |
| 适用场景 | 日常分析 | 关键优化决策 |
| 信息量 | BRI 数值 | BRI + 真实时间影响 |

---

## 方法 3: "宏传播路径追踪" (Macro Propagation Tracer)

### 原理

不记录宏使用次数，追踪从定义到使用的**完整传播链**。找出"宏传播枢纽" — 那些定义了被大量其他头文件传播使用的宏的文件。

### 为什么"非常规"

- 传统工具只统计"宏被用了多少次"
- 这个方法追踪"宏从哪里来、经过哪些中间文件、到哪里去"

### 适用场景

- 识别宏传播的关键节点（枢纽文件）
- 评估宏清理的优先级
- 检测宏条件性传播

### 实现伪代码

```python
class MacroPropagationTracer:
    """
    追踪宏从定义到使用的完整传播路径。
    """
    
    def __init__(self):
        self.macro_definitions = {}    # macro_name → definition_site
        self.macro_expansions = []     # 宏展开记录
        self.propagation_chains = []   # 传播链
    
    def trace_from_preprocessor_log(self, preprocessor_log, header_graph):
        """
        从预处理器日志构建传播链。
        
        preprocessor_log 包含:
        - 每次宏定义的位置
        - 每次宏展开的位置和条件栈
        """
        for use in preprocessor_log.macro_expansions:
            # 找宏定义位置
            definition = preprocessor_log.macro_definitions.get(use.name)
            if not definition:
                continue
            
            # 构建传播路径：定义文件 → include 链 → 使用文件
            path = self._build_propagation_path(
                definition.file,    # 宏定义在哪个头文件
                use.file,           # 宏在哪个文件展开
                header_graph,       # include 关系图
                use.condition_stack # 预处理条件栈
            )
            
            chain = PropagationChain(
                macro_name=use.name,
                definition_site=definition,
                expansion_site=use,
                path=path,
                path_length=len(path),
                is_conditional=use.condition_stack != [],
                condition=use.condition_stack
            )
            self.propagation_chains.append(chain)
        
        return self.propagation_chains
    
    def _build_propagation_path(self, def_file, use_file, graph, conditions):
        """构建宏从定义到使用的最短传播路径"""
        if def_file == use_file:
            return [def_file]
        
        # 在 include 图上找最短路径
        try:
            path = nx.shortest_path(graph, def_file, use_file)
            return path
        except nx.NetworkXNoPath:
            return [def_file, use_file]  # 直接关系
    
    def find_propagation_hubs(self):
        """
        找"宏传播枢纽" — 定义了被大量其他头文件传播的宏的文件。
        
        枢纽得分 = 所有宏的传播路径长度之和
        """
        hub_score = defaultdict(int)
        
        for chain in self.propagation_chains:
            definition_file = chain.definition_site.file
            hub_score[definition_file] += chain.path_length
        
        # 按得分排序
        hubs = sorted(hub_score.items(), key=lambda x: x[1], reverse=True)
        
        return [
            PropagationHub(
                file=hub,
                score=score,
                macros_defined=self._get_macros_defined_in(hub),
                propagation_depth=score
            )
            for hub, score in hubs
        ]
    
    def _get_macros_defined_in(self, file):
        """获取在指定文件中定义的所有宏"""
        return [
            chain.macro_name 
            for chain in self.propagation_chains 
            if chain.definition_site.file == file
        ]
    
    def analyze_conditional_propagation(self):
        """分析宏的条件性传播"""
        conditional_chains = [
            chain for chain in self.propagation_chains 
            if chain.is_conditional
        ]
        
        # 按条件分组
        by_condition = defaultdict(list)
        for chain in conditional_chains:
            condition_str = str(chain.condition)
            by_condition[condition_str].append(chain)
        
        return ConditionalPropagationReport(
            total_chains=len(self.propagation_chains),
            conditional_chains=len(conditional_chains),
            conditional_ratio=len(conditional_chains) / len(self.propagation_chains)
                if self.propagation_chains else 0,
            by_condition=by_condition
        )
```

### 与传统方法的对比

| 维度 | 宏使用次数统计 | 传播路径追踪 |
|------|--------------|-------------|
| 信息量 | 数量 | 数量 + 路径 + 枢纽 |
| 适用场景 | 快速概览 | 深度分析 + 清理优先级 |
| 识别枢纽 | 否 | 是 |
| 条件传播 | 否 | 是 |

---

## 方法 4: "前向声明覆盖率审计" (Forward-Declaration Coverage Audit)

### 原理

衡量项目中"多少指针/引用类型本可以用前向声明但用了完整 include"。这是一个**内聚度指标** — 高前向声明覆盖率说明代码结构良好。

### 为什么"非常规"

- 传统工具报告"依赖多不多"
- 这个方法报告"依赖有没有必要"

### 适用场景

- 评估 include 清理的收益
- 识别可以改用前向声明的地方
- 作为重构后的质量检查

### 实现伪代码

```python
class ForwardDeclAudit:
    """
    审计项目中前向声明的使用情况。
    """
    
    def __init__(self, symbol_graph):
        self.graph = symbol_graph
    
    def audit(self, headers):
        opportunities = []
        
        for header in headers:
            includes = self._get_direct_includes(header)
            
            for inc in includes:
                symbols_defined = self._get_symbols_defined_in(inc)
                
                for sym in symbols_defined:
                    usage = self._analyze_symbol_usage(header, sym)
                    
                    if usage.is_only_pointer_or_reference:
                        # 该符号在 header 中只被当作指针/引用使用
                        # → 可以前向声明替代 include
                        opportunities.append(ForwardDeclOpportunity(
                            header=header,
                            symbol=sym,
                            current_include=inc,
                            usage=usage,
                            estimated_bri_reduction=self._estimate_reduction(
                                header, inc, sym
                            )
                        ))
        
        return sorted(
            opportunities, 
            key=lambda o: o.estimated_bri_reduction, 
            reverse=True
        )
    
    def _analyze_symbol_usage(self, header, symbol):
        """分析符号在头文件中的使用方式"""
        # 在 AST 中找到所有对该符号的引用
        references = self._find_references(header, symbol)
        
        is_only_pointer = all(
            ref.is_pointer_context() for ref in references
        )
        is_only_reference = all(
            ref.is_reference_context() for ref in references
        )
        
        return SymbolUsage(
            symbol=symbol,
            reference_count=len(references),
            is_only_pointer_or_reference=is_only_pointer or is_only_reference,
            contexts=[ref.context for ref in references]
        )
    
    def _estimate_reduction(self, header, include, symbol):
        """估算如果改用前向声明，BRI 能降低多少"""
        # 该 include 的传递依赖数
        transitive_deps = self._count_transitive_dependencies(include)
        
        # 如果 50% 的用户只需要前向声明 → BRI 降低约 50%
        users_needing_full_def = self._count_users_needing_full_definition(
            include, symbol
        )
        users_total = self._count_users(include)
        
        if users_total == 0:
            return 0
        
        reduction_ratio = 1 - (users_needing_full_def / users_total)
        return transitive_deps * reduction_ratio
    
    def compute_coverage_ratio(self, headers):
        """计算前向声明覆盖率"""
        total_opportunities = 0
        already_using_fwd_decl = 0
        
        for header in headers:
            includes = self._get_direct_includes(header)
            for inc in includes:
                symbols = self._get_symbols_defined_in(inc)
                for sym in symbols:
                    usage = self._analyze_symbol_usage(header, sym)
                    if usage.is_only_pointer_or_reference:
                        total_opportunities += 1
                        if self._is_already_forward_declared(header, sym):
                            already_using_fwd_decl += 1
        
        return ForwardDeclCoverage(
            total_opportunities=total_opportunities,
            already_using_fwd_decl=already_using_fwd_decl,
            coverage_ratio=already_using_fwd_decl / total_opportunities
                if total_opportunities > 0 else 1.0
        )
```

### 与传统方法的对比

| 维度 | include 清理 | 前向声明审计 |
|------|-------------|-------------|
| 目标 | 减少不必要的 include | 识别可以前向声明的地方 |
| 输出 | 移除列表 | 改进机会列表 |
| 价值 | 短期清理 | 长期架构改善 |

---

## 方法 5: "循环依赖解剖器" (Cycle Autopsy)

### 原理

检测到循环依赖后，不是简单报告"有循环"，而是深入分析**循环的驱动力**，用最小割算法找最弱的断开边，给出精确的断开建议。

### 为什么"非常规"

- 传统工具报告"有循环依赖"就结束了
- 这个方法回答："为什么有循环？在哪里打破最有效？"

### 适用场景

- 循环依赖的根因分析
- 重构决策支持
- 评估打破循环的成本

### 实现伪代码

```python
class CycleAutopsy:
    """
    解剖循环依赖，找出最小的断开点。
    """
    
    def autopsy(self, cycle_files, dependency_graph):
        """
        对一个循环依赖进行解剖。
        """
        # Step 1: 构建循环内部的符号级依赖
        symbol_deps = []
        for f1 in cycle_files:
            for f2 in cycle_files:
                if f1 != f2:
                    deps = self._get_symbol_dependencies(f1, f2, dependency_graph)
                    symbol_deps.extend(deps)
        
        # Step 2: 用最小割算法找最弱的边
        G = nx.DiGraph()
        for dep in symbol_deps:
            # 权重 = 使用频率的倒数（使用越少 = 边越弱 = 越容易断开）
            G.add_edge(
                dep.from_file, dep.to_file,
                weight=1.0 / max(dep.usage_count, 1),
                symbol=dep.symbol_name
            )
        
        # 找最小割
        try:
            min_cut = nx.minimum_edge_cut(G)
        except nx.NetworkXError:
            min_cut = []
        
        # Step 3: 对每条可断开的边，给出具体建议
        suggestions = []
        for edge in min_cut:
            symbol = G[edge[0]][edge[1]]['symbol']
            strategy = self._recommend_strategy(symbol, edge)
            
            suggestions.append(CutSuggestion(
                from_file=edge[0],
                to_file=edge[1],
                symbol=symbol,
                strategy=strategy,
                confidence=self._estimate_confidence(strategy, symbol),
                estimated_bri_reduction=self._estimate_bri_reduction(
                    edge, cycle_files, dependency_graph
                )
            ))
        
        # Step 4: 评估循环严重程度
        severity = self._evaluate_severity(cycle_files, symbol_deps)
        
        return CycleAutopsyReport(
            cycle_files=cycle_files,
            symbol_dependencies=symbol_deps,
            cut_suggestions=suggestions,
            severity=severity,
            recommended_action=suggestions[0] if suggestions else None
        )
    
    def _recommend_strategy(self, symbol, edge):
        """根据符号类型推荐断开策略"""
        if self._is_type(symbol):
            return "前向声明：将完整 include 改为 forward declaration"
        elif self._is_function(symbol):
            return "接口提取：将函数声明提取到独立头文件"
        elif self._is_variable(symbol):
            return "依赖注入：将全局变量改为参数传递"
        elif self._is_macro(symbol):
            return "宏清理：将宏改为 constexpr 或 inline 函数"
        else:
            return "中间层：引入新模块作为依赖缓冲"
    
    def _evaluate_severity(self, cycle_files, symbol_deps):
        """评估循环的严重程度"""
        # 循环大小
        size = len(cycle_files)
        
        # 编译时间影响（估算）
        compile_impact = size * size  # O(n²) 级联效应
        
        # 修改传播（循环中任一文件修改 → 所有文件重编译）
        cascade_factor = size
        
        # 符号依赖密度
        symbol_density = len(symbol_deps) / (size * (size - 1))
        
        # 综合评分
        score = compile_impact * cascade_factor * (1 + symbol_density)
        
        if score > 1000:
            return Severity.CRITICAL
        elif score > 100:
            return Severity.HIGH
        elif score > 10:
            return Severity.MEDIUM
        else:
            return Severity.LOW
    
    def _estimate_bri_reduction(self, edge, cycle_files, graph):
        """估算断开某条边后 BRI 的降低量"""
        # 模拟断开
        simulated_graph = graph.copy()
        simulated_graph.remove_edge(edge[0], edge[1])
        
        # 重新计算循环中文件的 BRI
        old_bri = sum(
            self._compute_bri(f, graph) for f in cycle_files
        )
        new_bri = sum(
            self._compute_bri(f, simulated_graph) for f in cycle_files
        )
        
        return old_bri - new_bri
```

### 与传统方法的对比

| 维度 | 循环依赖检测 | 循环依赖解剖 |
|------|-------------|-------------|
| 输出 | "有循环" | "有循环 + 为什么 + 怎么打破" |
| 适用场景 | 发现问题 | 解决问题 |
| 工具价值 | 低（开发者知道有循环） | 高（开发者不知道怎么打破） |

---

## 方法 6: "耦合预算执行器" (Coupling Budget Enforcer)

### 原理

不是报告耦合问题，而是**阻断** — 超出耦合预算的 PR 直接 block，不允许合并。

### 为什么"非常规"

- 传统工具是被动报告
- 这个方法是主动阻断

### 适用场景

- CI/CD 中的自动化检查
- pre-commit hook
- PR 审核辅助

### 与传统方法的对比

| 维度 | 耦合度报告 | 耦合预算执行 |
|------|----------|-------------|
| 干预方式 | 被动（开发者看不看随意） | 主动（超预算就 block） |
| 效果 | 弱（开发者可能忽略） | 强（不修复就无法合并） |
| 适用场景 | 代码审查 | CI/CD 自动化 |

---

## 方法优先级排序

| 优先级 | 方法 | 投入 | 产出 | 推荐实施阶段 |
|--------|------|------|------|-------------|
| 1 | 自包含性爆破测试 | 中 | 高 | Phase 1（快速见效） |
| 2 | 耦合预算执行器 | 低 | 极高 | Phase 1（直接阻断） |
| 3 | 循环依赖解剖器 | 中 | 高 | Phase 2（深度分析） |
| 4 | 前向声明覆盖率审计 | 中 | 中 | Phase 2（架构改善） |
| 5 | 宏传播路径追踪 | 高 | 中 | Phase 3（专项分析） |
| 6 | 编译时间 A/B 测试 | 高 | 中 | Phase 4（验证优化） |

---

## 集成架构

```
┌─────────────────────────────────────────────────┐
│                检测方法层                         │
├─────────────┬──────────────┬────────────────────┤
│ 传统方法     │  非常规方法   │  混合验证           │
├─────────────┼──────────────┼────────────────────┤
│ BRI 计算     │ 自包含爆破   │ BRI + 爆破交叉验证  │
│ 循环检测     │ 循环解剖     │ 检测 + 解剖联合     │
│ 宏统计       │ 宏路径追踪   │ 统计 + 路径联合     │
│ include 分析 │ 前向声明审计 │ 分析 + 审计联合     │
└─────────────┴──────────────┴────────────────────┘
         │              │                │
         └──────────────┼────────────────┘
                        │
                ┌───────▼───────┐
                │  耦合预算执行  │ ← 超预算直接 block
                └───────┬───────┘
                        │
                ┌───────▼───────┐
                │   CI/CD 集成   │
                └───────────────┘
```

---

*Creative Disruptor — 团队 cpp-coupling-detection*
