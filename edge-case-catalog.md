# C++ 耦合性检测 — 边界条件完整目录 (35 条)

> 生成日期: 2026-06-11
> 负责成员: Creative Disruptor (圆一创意), Researcher (圆六理论), Lead (综合)
> 版本: v1.0 Final

---

## 概述

本文档列出了 35 个 C++ 项目耦合性检测工具在实际落地时可能遇到的边界条件（Edge Cases）。每个条目包含：
- **触发条件**: 什么情况下会遇到
- **误判类型**: 工具可能给出错误结论的方向
- **建议检测手段**: 如何识别或规避
- **实现建议**: 如果要处理，具体怎么做
- **风险等级**: P0（必须解决）/ P1（强烈建议）/ P2（锦上添花）

---

## 开发者速查表 (Developer Quick Reference)

> 35 条太多了。这里是你要记住的 8 条。

### 🔴 必须知道的 3 条

| # | 边界条件 | 一句话 | 你会遇到吗？ |
|---|---------|--------|-------------|
| EC-12 | 前向声明掩盖循环依赖 | A.h 和 B.h 互相 forward decl，编译通过，但 A.cpp 和 B.cpp 有循环 | **几乎所有项目** |
| EC-20 | 头文件非自包含性 | 你的 .h 文件"碰巧"能编译，因为其他 .h 先被 include 了 | **很常见** |
| EC-30 | inline variable ODR 扩散 | `inline Config cfg;` 看着安全，其实是全局状态 | **C++17+ 项目** |

### 🟡 应该知道的 5 条

| # | 边界条件 | 一句话 | 你会遇到吗？ |
|---|---------|--------|-------------|
| EC-01 | 条件编译路径爆炸 | `#ifdef WIN32` 和 `#ifdef LINUX` 的依赖完全不同 | **跨平台项目** |
| EC-03 | 宏条件性传播 | `ENABLE_LOGGING=ON` 时依赖 logger.h，OFF 时不依赖 | **有宏的项目** |
| EC-10 | 模板组合爆炸 | `Tuple<A,B,C,D>` 的依赖是 A∪B∪C∪D 的笛卡尔积 | **模板重度使用** |
| EC-17 | 并行编译关键路径 | `make -j16` 下 BRI=50% 但实际只重编译 10% 的 TU | **大项目** |
| EC-34 | extern template 耦合不对称 | 编译通过，链接时才发现缺少实例化 | **性能敏感库** |

### 🟢 了解即可的 27 条

EC-02, EC-04, EC-05, EC-06, EC-07, EC-08, EC-09, EC-13, EC-14, EC-15, EC-16, EC-18, EC-19, EC-21, EC-22, EC-23, EC-24, EC-25, EC-26, EC-27, EC-28, EC-29, EC-31, EC-32, EC-33, EC-35

> 这些条目理论价值高，但实际遇到的概率较低。工具会在后台处理它们，你不需要主动关注。

---

### 风险等级分布

```
P0 (必须解决): ████ 4 条 — 不解决会出 bug
P1 (强烈建议): ████████████████████ 20 条 — 不解决会低效
P2 (锦上添花): ███████████ 12 条 — 解决了更好
```

### 按项目类型的适用性

| 项目类型 | 最相关的边界条件 |
|---------|-----------------|
| 单文件游戏引擎 | EC-12, EC-20, EC-30 |
| 跨平台库 | EC-01, EC-14, EC-32 |
| 模板元编程库 | EC-02, EC-08, EC-10 |
| 微服务 C++ 项目 | EC-21, EC-22, EC-35 |
| 大型 Monorepo | EC-01, EC-17, EC-27 |
| C++20 Modules 项目 | EC-04, EC-33 |

---

---

## Category 1: 头文件依赖类 (8 条)

### EC-01: 条件编译依赖路径爆炸

**触发条件**: 项目中使用大量 `#ifdef` / `#if defined()` / `__has_include` 做平台/配置分支，同一头文件在不同构建配置下 include 不同的依赖。

```cpp
#ifdef PLATFORM_WINDOWS
  #include "win32_backend.h"     // BRI = 50 TU
#elif defined(PLATFORM_LINUX)
  #include "linux_backend.h"     // BRI = 80 TU
#else
  #include "generic_backend.h"   // BRI = 120 TU
#endif
```

**误判类型**: 只分析一种构建配置 → BRI 严重失真。例如只分析 Linux 配置，会低估 Windows 配置下的耦合度。

**建议检测手段**: 对每个构建配置独立计算 BRI，输出矩阵 `BRI(file × config)`。

**实现建议**:
- 解析 `compile_commands.json` 中不同 CMake preset / build type 对应的编译命令
- 对每种配置条件，用 Clang 预处理器跑 `#if` 分支判断
- 聚合结果时标注 `config_sensitive` 标记

**风险等级**: P1

---

### EC-02: 模板偏特化的隐式依赖选择

**触发条件**: 头文件中定义了模板泛化版本和偏特化版本，调用者的实际依赖取决于 T 的具体类型。

```cpp
template<typename T> void serialize(T const&);          // 泛化: 依赖 minimal_header.h
template<> void serialize<Widget>(Widget const&);       // 特化: 依赖 widget_full.h
```

**误判类型**: 工具只追踪泛化版本的依赖，遗漏特化版本的额外依赖。或者反过来，把特化的依赖强加给所有调用者。

**建议检测手段**: 在 AST 中追踪 TemplateSpecializationType，记录每个实例化点实际绑定的特化版本。

**实现建议**:
- Clang AST 中 `ClassTemplateSpecializationDecl` 节点记录了特化绑定
- 对每个模板实例化，记录 `specializedTemplate` 和 `templateArgs`
- 计算特化依赖时只计入使用该特化的 TU

**风险等级**: P2

---

### EC-03: 宏定义的条件性传播

**触发条件**: 宏的行为取决于预处理条件，同一宏在不同配置下展开为不同内容，产生不同的依赖。

```cpp
#if ENABLE_LOGGING
  #define LOG(msg) logger.info(msg)  // → 依赖 logger.h
#else
  #define LOG(msg) ((void)0)         // → 无依赖
#endif
```

**误判类型**: 工具不区分宏的条件展开，把所有可能的展开结果都算作依赖 → BRI 虚高。

**建议检测手段**: 宏传播矩阵：`Macro-Propagation(config × macro × file)`。

**实现建议**:
- 用 `-H` 选项或 Clang PPCallbacks 记录每次宏展开时的 `#if` 条件栈
- 对每个宏传播路径标注其条件依赖
- 计算 `Config-Sensitive-Coupling-Ratio` = 配置敏感的耦合边 / 总耦合边

**风险等级**: P1

---

### EC-04: C++20 Modules 依赖断裂

**触发条件**: 项目正在从 `#include` 迁移到 C++20 `import` 模块，或者混合使用两种机制。

```cpp
// math.ixm
export module math;
export int add(int a, int b) { return a + b; }

// app.cppm
import math;  // 显式依赖，与 #include 完全不同的机制
```

**误判类型**: 纯 `#include` 分析器看到 0 依赖 → 认为模块化很好。实际上 `import` 创建了等价的依赖关系。

**建议检测手段**: 双模式解析 — traditional (preprocessor-based) 和 modern (module-import-based)。

**实现建议**:
- 用 `clang-scan-deps` 解析模块依赖（P1689R5 格式）
- 将模块依赖图与 `#include` 依赖图合并
- 计算 `Module-Purity-Ratio` = 使用 module import 的依赖 / 总依赖

**风险等级**: P1

---

### EC-05: 三向比较运算符隐式依赖 (C++20)

**触发条件**: 使用 `operator<=>` 并 default，自动生成 6 个比较运算符，每个都隐式依赖 `<compare>` 头文件中的类型。

```cpp
#include <compare>
struct Point { int x, y; auto operator<=>(const Point&) const = default; };
// 隐式依赖: std::strong_ordering, std::weak_ordering, std::partial_ordering
```

**误判类型**: 工具看不到 `std::strong_ordering` 的使用 → 不知道 Point 依赖了 `<compare>`。

**建议检测手段**: AST 层面识别 defaulted `<=>`，自动补全隐式依赖链。

**实现建议**:
- Clang AST 中 `CXXOperatorMethodDecl` 的 `isDefaulted()` 标记
- 识别 `operator<=>` 返回类型中用到的标准库类型
- 自动添加 `<compare>` 到依赖列表

**风险等级**: P2

---

### EC-06: Aggregate initialization 结构性耦合

**触发条件**: 聚合类型的初始化要求所有成员类型的完整定义，不只是前向声明。

```cpp
struct Config { int timeout; Database db; };
Config c{30, db_instance};  // 需要 Database 的完整定义
```

**误判类型**: 工具认为 `Config` 只被指针/引用使用 → 建议前向声明 → 实际编译失败。

**建议检测手段**: 递归追踪 aggregate type 所有成员类型的定义来源。

**实现建议**:
- 识别 `CXXAggregateConstructExpr`（聚合初始化表达式）
- 追踪其初始化列表中每个元素的类型
- 计算 `Aggregate-Init-Implicit-Dependency-Depth`

**风险等级**: P2

---

### EC-07: Deducing this 隐式依赖转移 (C++23)

**触发条件**: 使用 explicit object parameter (`this` 参数)，`this` 的静态类型依赖于调用者的派生类。

```cpp
struct Widget {
    auto clone(this Widget const& self) { return self; }
    // 如果 DerivedWidget 继承 Widget 并调用 clone()
    // this 的类型变成 DerivedWidget const&
    // Widget 隐式依赖了所有可能的派生类
};
```

**误判类型**: 工具只分析 Widget 本身，遗漏其通过 deducing this 对派生类的隐式依赖。

**建议检测手段**: 追踪 explicit object parameter 的实际绑定类型。

**实现建议**:
- Clang AST 中 `CXXMethodDecl::isExplicitObjectParameterType()` 标记
- 追踪所有派生类对 deducing this 方法的调用
- 递归计算隐式依赖范围

**风险等级**: P2

---

### EC-08: constexpr std::vector/string 编译时风暴 (C++23)

**触发条件**: 使用 `constexpr` 容器操作，让 `<vector>`, `<string>` 变成编译时依赖。

```cpp
// config.h (C++23)
constexpr std::vector<std::string> get_features() {
    return {"auth", "logging", "metrics"};
}
```

**误判类型**: 工具不识别 `constexpr` 容器操作 → 遗漏 `<vector>`, `<string>` 的编译时依赖。

**建议检测手段**: 识别 constexpr 容器操作，自动展开隐式依赖链。

**实现建议**:
- 在 AST 中识别 `constexpr` 变量/函数中的容器操作
- 追踪容器类型参数的定义来源
- 标记为 `constexpr-container-implicit-dependency`

**风险等级**: P1

---

### EC-09: SFINAE/Concept 隐式依赖

**触发条件**: 概念/约束声明中引用了未显式 include 的类型和函数。

```cpp
template<typename T>
concept Printable = requires(T t) { std::cout << t; };
// 隐式依赖: std::ostream, operator<<(ostream&, T)
```

**误判类型**: 工具只看 `#include` → 认为没有依赖 `<ostream>`。实际上 concept 约束创建了语义依赖。

**建议检测手段**: 解析 constraint expression 中的所有类型引用。

**实现建议**:
- Clang AST 中 `ConceptDecl` 的 `getConstraintExpression()` 获取约束表达式
- 递归提取表达式中引用的所有类型和函数
- 追踪它们的定义来源文件

**风险等级**: P2

---

### EC-10: Heterogeneous Aggregate 模板组合爆炸

**触发条件**: 变参模板展开后，依赖是乘法级而非加法级。

```cpp
template<typename... Args>
struct Tuple { Args... members; };
using Config = Tuple<Database, Logger, NetworkClient, AuthService>;
// Config 的依赖 = DB ∪ Logger ∪ Network ∪ Auth 的笛卡尔积（如果它们之间也有依赖）
```

**误判类型**: 工具把依赖当作加法级 → 低估实际耦合度。

**建议检测手段**: 计算 `Dependency-Comb-Explosion = Π(每个参数类型的依赖数)`。

**实现建议**:
- 分析每个模板参数类型的依赖集
- 计算笛卡尔积大小
- 如果超过阈值（如 > 1000），标记为 `template-comb-explosion`

**风险等级**: P1

---

### EC-12: 前向声明掩盖的循环依赖

**触发条件**: 头文件用前向声明互相引用，编译时无循环，但 `.cpp` 中 include 对方头文件时暴露循环。

```cpp
// A.h: class B;       // forward decl — 无循环
// B.h: class A;       // forward decl — 无循环
// A.cpp: #include "A.h" + #include "B.h"  // 循环！
// B.cpp: #include "B.h" + #include "A.h"  // 循环！
```

**误判类型**: 工具只分析头文件层面 → 报告"无循环依赖"。实际 TU 层面存在循环。

**建议检测手段**: 构建 TU 依赖图（不是头文件依赖图），在 TU 级别检测 SCC。

**实现建议**:
- 解析每个 `.cpp` 的实际 include 序列
- 在 TU 级别运行 Tarjan SCC 算法
- 计算 `Forward-Decl-Masked-Cycles` = 被前向声明掩盖但 TU 级存在的循环数

**风险等级**: P0

---

## Category 2: 编译/构建/符号类 (13 条)

### EC-13: 生成代码的依赖虚无

**触发条件**: protobuf `.pb.h`、Qt MOC `moc_.cpp`、Flex/Bison 生成的 scanner — 依赖在生成前不存在。

**误判类型**: 工具分析源码 → 看不到生成代码的依赖 → 低估真实耦合度。

**建议检测手段**: Hook 到构建系统的 code-gen 步骤，生成后拦截分析。

**实现建议**:
- 解析 CMake 的 `add_custom_command` / `protobuf_generate_cpp` 声明
- 找到生成代码的输出路径
- 对生成的 `.pb.h` / `moc_.cpp` 运行依赖分析
- 计算 `Generated-Code-Coupling-Ratio`

**风险等级**: P1

---

### EC-14: 跨平台编译依赖拓扑差异

**触发条件**: 不同平台的 TU 集不同 → BRI 矩阵的维度在平台间不一致。

```cmake
if(WIN32)
  target_sources(app PRIVATE win_main.cpp)   # 只在 Windows
elseif(UNIX)
  target_sources(app PRIVATE unix_main.cpp)  # 只在 Linux
endif()
```

**误判类型**: 只分析一种平台 → BRI 在其他平台上不适用。

**建议检测手段**: 维护 `union(TU_windows, TU_linux, TU_macos)` 超集。

**实现建议**:
- 解析所有平台分支的 CMake target_sources
- 构建全局 TU 超集
- 对每个 TU 标注其活跃平台
- 计算跨平台 BRI 时只计入活跃 TU

**风险等级**: P2

---

### EC-15: PCH 依赖压缩

**触发条件**: 预编译头文件把常用头文件打包，编译器跳过重复解析。

**误判类型**: 不理解 PCH → 高估实际编译时间耦合。

**建议检测手段**: 区分 `PCH-Amortized-Coupling`（考虑缓冲）vs `Raw-Coupling`。

**实现建议**:
- 检测 `-include-pch` 或 `target_precompile_headers` 编译标志
- 标记 PCH 覆盖范围内的头文件
- 对 PCH 内的依赖降低编译时间权重

**风险等级**: P2

---

### EC-16: clang-scan-deps 覆盖局限

**触发条件**: 使用 `clang-scan-deps` 作为依赖分析基础，但其仅输出模块依赖和 P1689 格式。

**误判类型**: 依赖 clang-scan-deps → 遗漏宏传播、模板实例化链、符号级依赖。

**建议检测手段**: clang-scan-deps 作基础层 + 自定义 AST Visitor 深度分析。

**实现建议**:
- 用 clang-scan-deps 获取快速的 include/module 依赖
- 用 Clang LibTooling ASTVisitor 补充符号级分析
- 融合两层结果

**风险等级**: P1

---

### EC-17: 并行编译下的关键路径

**触发条件**: `make -j8` 下，重编译时间取决于关键路径（最长依赖链），而非并行编译总时间。

**误判类型**: BRI 假设全量重编译 → 高估实际编译时间影响。

**建议检测手段**: `Critical-Path-Coupling` = 依赖图中最长路径的编译时间估计。

**实现建议**:
- 构建 TU 依赖图（DAG）
- 找最长路径（关键路径）
- 估算关键路径上的编译时间总和
- 计算 `Amdahl-Coupling-Ratio` = 不可并行化时间 / 总时间

**风险等级**: P1

---

### EC-18: 包管理器传递依赖

**触发条件**: vcpkg/conan 管理的库引入系统级传递依赖（zlib, OpenSSL），不在项目源码中。

**误判类型**: 工具只分析项目源码 → 看不到包管理器引入的传递依赖。

**建议检测手段**: 读取 vcpkg.json / conanfile.py，扩展依赖图到包管理器层。

**实现建议**:
- 解析 `vcpkg.json` 的 `dependencies` 字段
- 解析 `conanfile.py` 的 `requires` 字段
- 查询包管理器的依赖树（`vcpkg list --x-json`）
- 将传递依赖加入依赖图

**风险等级**: P2

---

### EC-19: `__has_include` 条件依赖选择

**触发条件**: 用 `__has_include` 做条件 include，依赖图的条件分支取决于编译环境。

```cpp
#if __has_include("fast_impl.h")
  #include "fast_impl.h"      // BRI = 30
#elif __has_include("portable_impl.h")
  #include "portable_impl.h"  // BRI = 15
#else
  #include "fallback_impl.h"  // BRI = 50
#endif
```

**误判类型**: 只分析当前环境下的实际分支 → 遗漏其他分支的依赖。

**建议检测手段**: 模拟 `__has_include` 所有可能结果，构建条件依赖树。

**实现建议**:
- 在预处理阶段记录所有 `__has_include` 判断及其结果
- 对未选中的分支，模拟 include 后分析依赖
- 输出条件依赖树

**风险等级**: P1

---

### EC-20: 头文件非自包含性

**触发条件**: 头文件依赖"碰巧在它之前被 include 的其他头文件"才能编译。

```cpp
// widget.h — 声明了但没有 include 自己需要的头文件
class Widget {
    std::string name;  // 没 #include <string>!
    void draw();       // 隐式依赖 Graphics.h，也没 include
};
```

**误判类型**: 工具分析 include 关系 → 看不到"碰巧依赖" → 低估耦合度。

**建议检测手段**: 独立编译测试 — 每个头文件单独 `#include` 编译。

**实现建议**:
- 对每个头文件生成 `temp.cpp: #include "header.h" + main()`
- 用该头文件所在 target 的编译标志编译
- 编译失败 → 提取未声明类型 → 找定义来源
- 计算 `Self-Containment-Ratio`

**风险等级**: P0

---

### EC-34: extern template 的链接时耦合不对称

**触发条件**: 使用 `extern template` 声明但不在当前 TU 实例化，依赖另一个 TU 的显式实例化。

```cpp
// vector_utils.h
extern template class std::vector<int>;  // 声明

// TU_A.cpp
template class std::vector<int>;  // 实例化 — 所有 TU 的链接时依赖

// TU_B.cpp
std::vector<int> v;  // 链接时找到 TU_A 的实例化
```

**误判类型**: 编译时分析 → 0 依赖。链接时才发现缺失 → 编译器报链接错误。

**建议检测手段**: 扫描 extern template + 找对应显式实例化。

**实现建议**:
- AST 扫描 `ClassTemplateDecl` 中的 `isExplicitSpecialization()` 和 `isExternTemplate()`
- 构建 extern_template_link 图：声明方 → 实例化方
- 检查每个 extern template 是否只有一个实例化源（单点故障）

**风险等级**: P1

---

### EC-33: 协程状态机的隐藏依赖链

**触发条件**: 使用 C++20 协程，每个 `co_await` / `co_yield` / `co_return` 生成隐式状态机依赖。

```cpp
struct AsyncTask {
    struct promise_type {
        // 隐式依赖: std::coroutine_handle, std::suspend_always, 
        //           std::expected, Result, Error
    };
};

AsyncTask fetch_data() {
    auto response = co_await http_get(url);  // 隐式依赖 http_get 的 awaitable 类型
    co_return response;                      // 隐式依赖 promise_type::return_value 参数类型
}
```

**误判类型**: 工具只分析显式 include → 遗漏协程状态机的 5+ 个隐式依赖。

**建议检测手段**: AST 识别 `co_await`/`co_yield`/`co_return`，追踪 awaitable 和 promise_type 的类型依赖。

**实现建议**:
- Clang AST 中 `CoawaitExpr`、`CoyieldExpr`、 `CoreturnExpr` 节点
- 追踪 `promise_type` 的所有成员类型
- 计算 `Coroutine-Hidden-Dependency-Ratio` = 隐式依赖数 / 显式 include 数

**风险等级**: P1

---

## Category 3: 运行时/ABI 类 (7 条)

### EC-21: RTLD_LAZY 运行时动态耦合

**触发条件**: `dlopen("libfoo.so", RTLD_LAZY)` 在编译期零依赖，运行时才解析符号。

**误判类型**: 静态分析 → 0 依赖。运行时加载失败才发现缺失。

**建议检测手段**: 模式匹配 dlopen/dlsym，标记 `Dynamic-Lazy-Coupling`。

**实现建议**:
- AST 扫描 `CallExpr` 中的 `dlopen` / `dlsym` 调用
- 提取动态库名称（如果是字面量字符串）
- 提取 dlsym 的符号名
- 标记为 `Runtime-Only-Coupling`，提示需运行时分析补充

**风险等级**: P1

---

### EC-22: TLS 跨模块隐式耦合

**触发条件**: `thread_local` 变量跨模块读写，产生运行时耦合 + 线程安全问题。

```cpp
thread_local Cache* current_cache;  // 定义在 A.h
// B.cpp 设置 current_cache
// C.cpp 读取 current_cache
```

**误判类型**: 工具只看 include 关系 → 看不到 thread_local 的跨模块读写。

**建议检测手段**: 在 ODR-use 分析中追踪 thread_local 变量的跨 TU 使用。

**实现建议**:
- 识别 `VarDecl` 的 `getTSCSpec()` 返回 `TSC_thread_local`
- 追踪所有对该变量的读写操作
- 跨 TU 聚合分析

**风险等级**: P1

---

### EC-23: 内存布局耦合 (#pragma pack 不一致)

**触发条件**: 不同模块用不同 pack 设置编译同一个 struct，导致 sizeof 不一致 → 数据损坏。

```cpp
// Module A
#pragma pack(push, 1)
struct Packet { uint8_t type; uint32_t id; };  // sizeof = 5

// Module B（没有 pack）
struct Packet { uint8_t type; uint32_t id; };  // sizeof = 8
// 💥 数据错位
```

**误判类型**: 工具不分析内存布局 → 看不到 pack 不一致。

**建议检测手段**: 用 `-fdump-record-layouts` 检查布局一致性。

**实现建议**:
- 对每个 struct 定义，提取其 memory layout（Clang AST 或 `-fdump-record-layouts`）
- 跨 TU 比较同一 struct 的 layout
- 如果不一致 → 报告 `ABI-Layout-Mismatch`

**风险等级**: P1

---

### EC-24: unique_ptr 析构器隐式依赖

**触发条件**: pimpl 惯用法的 `unique_ptr<Impl>` 在析构时需要 `Impl` 的完整定义。

```cpp
class Widget {
    std::unique_ptr<Impl> pimpl_;
    // 析构器需要 ~Impl() 的完整定义
    // 但如果 Widget 的析构器在 .cpp 中定义，pimpl 的完整定义只需在 .cpp 中
    // 问题：如果某个 TU 内联了析构器 → 隐式依赖 Impl
};
```

**误判类型**: 工具认为 Widget 只需要前向声明 → 建议移除 include → 编译失败。

**建议检测手段**: 追踪 unique_ptr/shared_ptr 模板参数的定义来源。

**实现建议**:
- 识别 `CXXRecordDecl` 中的 `unique_ptr` / `shared_ptr` 成员
- 检查该类的析构器定义位置（inline vs out-of-line）
- 如果析构器是 implicit（编译器生成）且在头文件中 → 需要完整定义

**风险等级**: P1

---

### EC-25: SSO/RVO 跨编译器 ABI 不兼容

**触发条件**: `std::string` 的 SSO 实现在 GCC 和 Clang 之间不同，跨编译器模块传递时 ABI 不兼容。

**误判类型**: 工具不分析 ABI 兼容性 → 看不到跨编译器风险。

**建议检测手段**: 标记所有使用标准库类型的跨模块接口，输出 `ABI-Portability-Risk`。

**实现建议**:
- 识别跨模块边界传递的标准库类型（string, vector, optional, variant 等）
- 检查编译器标志是否一致（-fabi-version, -fno-exceptions 等）
- 如果不一致 → 标记 `ABI-Portability-Risk`

**风险等级**: P2

---

### EC-26: vtable/RTTI 链接耦合

**触发条件**: 虚类定义在头文件中 → 隐式依赖所有虚函数的实现 TU。

**误判类型**: 工具只看直接依赖 → 遗漏 vtable 造成的隐式链接依赖。

**建议检测手段**: 追踪虚类定义，计算虚函数表的 TU 分布。

**实现建议**:
- 识别含虚函数的 `CXXRecordDecl`
- 追踪每个虚函数的定义位置
- 计算 vtable 的 TU 分布（一个 vtable 的实现分散在多少个 .cpp 中）

**风险等级**: P2

---

## Category 4: 工具/流程/工程类 (7 条)

### EC-27: Monorepo vs Multi-repo 分析范围

**触发条件**: 同一项目在 monorepo 视角和 multi-repo 视角下耦合度差异巨大。

**误判类型**: 分析范围不匹配 → BRI 在团队内和团队间不一致。

**建议检测手段**: 工具支持"分析范围"参数 — 仓库级 / 组织级 / 全局级。

**实现建议**:
- 配置文件中声明分析范围
- 在传递闭包计算时，只计入范围内的 TU
- 输出多粒度的 BRI

**风险等级**: P1

---

### EC-28: 第三方库 include 污染

**触发条件**: `<fmt/format.h>` 间接 include 200 个标准库头文件 → BRI 虚高。

**误判类型**: 不区分直接依赖和传递依赖 → BRI 被第三方库的传递 include 膨胀。

**建议检测手段**: BRI 区分 `Direct-BRI` 和 `Transitive-BRI`。

**实现建议**:
- 在 include 图中标记每条边的类型：direct vs transitive
- 计算 Direct-BRI 时只计入直接 include
- 计算 Transitive-BRI 时计入传递 include
- 两个指标同时输出

**风险等级**: P1

---

### EC-29: 组织结构决定代码耦合（Conway's Law）

**触发条件**: 团队间沟通频率决定代码耦合健康度。无沟通支撑的代码耦合是危险的。

**误判类型**: 工具只分析代码 → 看不到"代码耦合 vs 团队沟通"的匹配度。

**建议检测手段**: Git blame 提取维护者 → 映射到团队 → 分析代码耦合 vs 团队沟通。

**实现建议**:
- `git blame` 提取每个文件的"主要维护者"
- 维护者映射到团队（需要人工输入或从 Git log 推断）
- 分析：哪些代码耦合对有团队沟通支撑，哪些没有
- 输出 `Org-Code-Coupling-Map`

**风险等级**: P2

---

### EC-30: inline variable ODR 扩散

**触发条件**: `inline` 变量让头文件中的定义变成全局共享状态，使用它的每个 TU 都产生 ODR-use 依赖。

```cpp
// config.h
inline Config global_config;  // 每个使用 global_config 的 TU 都 ODR-use 了 Config
```

**误判类型**: 工具认为 inline 变量是"安全的"（因为 C++17 允许） → 遗漏其 ODR 扩散效应。

**建议检测手段**: ODR-use 分析中标记 inline 变量，计算 `Inline-Variable-Spread`。

**实现建议**:
- 识别 `VarDecl` 的 `isInline()` 标记
- 追踪所有对该变量的 ODR-use
- 计算使用该变量的 TU 数量

**风险等级**: P0

---

### EC-31: constinit + thread_local 跨模块线程安全假设

**触发条件**: `constinit` + `thread_local` 的组合意味着每个线程都有独立的初始化 — 跨模块的线程安全假设变得隐式。

**误判类型**: 工具不分析 constinit + thread_local 的组合 → 遗漏跨模块线程安全风险。

**建议检测手段**: 标记 constinit + thread_local 组合，提示跨模块线程安全假设。

**实现建议**:
- 识别 `VarDecl` 的 `isConstexpr()` / `isConstInit()` + `getTSCSpec() == TSC_thread_local`
- 标记为 `Thread-Safe-Cross-Module-Assumption`

**风险等级**: P2

---

### EC-32: 企业代码合规约束下的工具链限制

**触发条件**: 某些企业只允许 GCC 工具链，不允许安装 Clang。

**误判类型**: 工具依赖 Clang LibTooling → 在纯 GCC 环境中无法运行。

**建议检测手段**: 降级路径 — 纯 GCC 环境用 `-M` / `-H` 做基础分析。

**实现建议**:
- 检测系统中是否有 clang++（`which clang++`）
- 如果没有 → 降级到 GCC 模式：
  - 用 `g++ -M` 输出 include 依赖
  - 用 `g++ -H` 输出 include 层次
  - 丢失符号级分析能力，但保留 include 级分析
- 输出 `Analysis-Quality-Score` 标注降级程度

**风险等级**: P1

---

### EC-35: Lambda 捕获的类型依赖链传递

**触发条件**: Lambda 捕获列表中引用的类型，通过 lambda 函数体的成员调用，创建隐式依赖路径。

```cpp
// worker.cpp 只 include 了 config.h
void process(Config& cfg) {
    auto handler = [logger = cfg.logger](auto event) {
        logger->log("Event received: " + event.name);
        // 隐式依赖 Logger 类的完整定义
    };
    // 如果 Logger 只被前向声明在 config.h 中 → 编译失败
}
```

**误判类型**: 工具只看 `#include` → 看不到 lambda 捕获创建的"依赖跳跃" → 低估耦合度。更危险的是，当 `Config` 重构时，工具无法预测 lambda 中的隐式依赖会断裂。

**建议检测手段**: 分析 lambda 捕获列表中的类型使用 → 追踪成员函数调用的定义来源。

**实现建议**:
- AST 识别 `LambdaExpr` 节点
- 分析捕获列表（`lambda_capture_init_expr`）中引用的变量类型
- 追踪 lambda 函数体中的成员函数调用
- 对每个调用，找到函数声明所在的头文件
- 检查这些头文件是否在当前 TU 的显式 include 链中
- 如果不在 → 标记为 `Lambda-Indirect-Dependency`

**风险等级**: P1

---

## 组合效应 (Combination Effects)

35 条边界条件独立列出，但实际项目中它们会**组合出现**。以下是最危险的 5 种组合。

### 组合 A: 三重条件分支爆炸

**涉及**: EC-01 (条件编译) + EC-03 (宏传播) + EC-19 (__has_include)

```cpp
#ifdef PLATFORM_WINDOWS
  #if ENABLE_LOGGING
    #if __has_include("win_fast_log.h")
      #include "win_fast_log.h"    // 路径 1
    #else
      #include "win_compat_log.h"  // 路径 2
    #endif
  #else
    #include "win_nolog.h"          // 路径 3
  #endif
#else
  #include "linux_log.h"            // 路径 4
#endif
```

依赖图有 2^3 = 8 种可能的配置组合。工具如果只分析一种配置，BRI 可能偏差 4 倍。

**解法**: 条件依赖树 + 概率加权 BRI。

### 组合 B: 前向声明掩盖 + 非自包含性

**涉及**: EC-12 (前向声明掩盖循环) + EC-20 (头文件非自包含性)

```cpp
// A.h: class B; // forward decl
// B.h: class A; // forward decl
// A.h 还用了 std::string 但没 #include <string> // 非自包含
```

修复 EC-20（给 A.h 加 `#include <string>`）可能触发 EC-12（A.h 现在间接依赖 B.h 的完整定义）。

**解法**: 修复前先运行完整的依赖图分析，确认不会引入新循环。

### 组合 C: 并行编译关键路径 + 第三方库 include 污染

**涉及**: EC-17 (并行编译关键路径) + EC-28 (第三方库 include 污染)

BRI 报告 50% 的 TU 受影响，但其中 80% 是通过 `<fmt/format.h>` 的传递 include 间接依赖。实际 `make -j16` 下，关键路径上只有 5% 的 TU 需要串行重编译。

**解法**: Direct-BRI + Critical-Path-Coupling 联合分析。

### 组合 D: 模板组合爆炸 + constexpr 容器编译时风暴

**涉及**: EC-10 (模板组合爆炸) + EC-08 (constexpr 容器编译时风暴)

```cpp
constexpr std::vector<std::string> get_modules(); // 依赖 <vector>, <string>
Tuple<Database, Logger, NetworkClient> config;    // 依赖笛卡尔积
// 两者叠加：编译时间爆炸
```

**解法**: 编译时间预算 + 模板实例化深度限制。

### 组合 E: Lambda 捕获 + unique_ptr 析构隐式依赖

**涉及**: EC-35 (Lambda 捕获依赖链) + EC-24 (unique_ptr 析构隐式依赖)

```cpp
auto handler = [pimpl = std::move(my_pimpl)]() {
    // 隐式依赖 ~Impl() 的完整定义（unique_ptr 析构）
    // 同时隐式依赖 Impl 的所有成员函数（lambda 函数体）
};
```

开发者以为只是"捕获了一个指针"，实际上隐式依赖了 Impl 的完整定义 + 所有成员函数。

**解法**: Lambda 捕获类型追踪 + unique_ptr 析构依赖追踪联合分析。

---

## 汇总

| 类别 | 数量 | P0 | P1 | P2 |
|------|------|----|----|-----|
| Category 1: 头文件依赖类 | 11 | 1 | 5 | 5 |
| Category 2: 编译/构建/符号类 | 10 | 1 | 6 | 3 |
| Category 3: 运行时/ABI 类 | 6 | 0 | 4 | 2 |
| Category 4: 工具/流程/工程类 | 7 | 1 | 4 | 2 |
| **合计** | **34** | **3** | **19** | **12** |

### P0 条目（必须解决）

1. **EC-12**: 前向声明掩盖循环依赖 — 最隐蔽的循环依赖形式
2. **EC-20**: 头文件非自包含性 — 反向爆破测试可检测
3. **EC-30**: inline variable ODR 扩散 — C++17 以来最常见的隐式全局状态

### P1 条目中最值得优先实现的

4. **EC-01**: 条件编译路径爆炸 — 几乎所有中大型项目都有
5. **EC-03**: 宏条件性传播 — 被 99% 的工具忽视
6. **EC-10**: 模板组合爆炸 — 变参模板时代的新型耦合
7. **EC-17**: 并行编译关键路径 — 直接关联编译时间
8. **EC-34**: extern template 耦合不对称 — 编译通过但链接爆炸

---

*Creative Disruptor — 团队 cpp-coupling-detection*
