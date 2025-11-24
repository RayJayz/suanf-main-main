# 智能排课系统 - 基于遗传算法的完整解决方案

> 一个功能完备的智能排课系统,采用高级遗传算法解决复杂的课程排课优化问题

[![Python Version](https://img.shields.io/badge/python-3.9%2B-blue)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

---

## 📋 目录

- [系统概述](#系统概述)
- [核心特性](#核心特性)
- [项目结构](#项目结构)
- [快速开始](#快速开始)
- [使用指南](#使用指南)
- [优化策略](#优化策略)
- [常见问题](#常见问题)
- [文档索引](#文档索引)

---

## 系统概述

本系统采用遗传算法实现智能排课,在满足硬性约束(教师/班级/教室时间冲突、容量限制等)的前提下,通过优化软约束(教室利用率、连续性、教师偏好等)生成高质量排课方案。

### 🎯 设计目标

- ✅ **零冲突**: 确保教师、班级、教室无时间冲突
- ✅ **高覆盖率**: 尽可能将所有课程安排入课表
- ✅ **高利用率**: 优化教室利用率(目标 75%-90%)
- ✅ **连续性优化**: 同一教师/班级连续课程尽量在同一教室
- ✅ **智能分配**: 必修课优先白天,选修课灵活安排

---

## 核心特性

### 🧬 遗传算法核心

- **智能个体生成**: 按优先级排序(长课优先、必修优先、大班优先)
- **适应度评估**: 硬约束 + 软约束综合评分体系
- **多样化遗传操作**: 单点交叉、多种变异类型(教师/时间/教室/智能修复)
- **精英保留策略**: 保护优秀个体,加速收敛
- **早停机制**: 停滞检测,避免无效迭代

### 🎨 约束体系

**硬约束**(-99999 至 -5000 分):

- 班级冲突: -80000(最高优先级)
- 教室容量不足: -60000(硬性要求)
- 教师冲突: -50000
- 教室冲突: -50000
- 周末排课: -10000（实际代码中无周末排课）
- 教师黑名单: -8000
- 设施不满足: -8000

**软约束**(30-400 分):

- 必修课晚上: 400
- 教室连续性: 300(优化后)
- 教室利用率: 200
- 教师偏好: 100

### 📊 四维度结果导出

Excel 导出包含四个视角:

1. **周期视角**: 按周一至周日查看每天课程安排
2. **教师视角**: 每位教师的完整课表
3. **班级视角**: 每个班级的完整课表
4. **教室视角**: 每个教室的使用情况

---

## 项目结构

```
d:\suanf-main-main/
├── suan2.py                           # 主程序入口
├── genetic_algorithm.py               # 遗传算法核心(1294行,优化版)
├── data_models.py                     # 数据模型定义
├── db_connector.py                    # 数据库连接与数据加载
├── view_schedule.py                   # 结果查看与Excel导出(四视角)
├── analyze_conflicts.py               # 冲突分析工具
├── check_data_scale.py                # 数据规模检查与参数推荐
├── test_data_generator.py             # 测试数据生成器
├── new.sql                            # 数据库表结构脚本
├── 排课系统说明.md                    # 📘 系统完整说明文档
├── 排课问题诊断与解决方案.md          # 🔧 问题诊断与解决手册
└── README.md                          # 本文件
```

---

## 快速开始

### 环境要求

- Python 3.9+
- PyMySQL
- openpyxl
- MySQL 5.7+ 或 MariaDB 10.3+

### 1. 安装依赖

```powershell
# 创建虚拟环境(推荐)
python -m venv .venv
.\.venv\Scripts\activate

# 安装依赖
pip install pymysql openpyxl
```

### 2. 配置数据库

```powershell
# 设置数据库连接(环境变量)
$env:DB_HOST = "localhost"
$env:DB_USER = "root"
$env:DB_PASSWORD = "20051113Da"
$env:DB_NAME = "paike2"
```

```sql
-- 创建数据库
CREATE DATABASE `paike2` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- 导入表结构
-- 使用 new.sql
--# 登录MySQL
--mysql -u [用户名] -p

--# 创建一个空数据库（如果还没有的话）
--CREATE DATABASE college_scheduler;

--# 退出MySQL
--exit;

--# 在命令行中，将.sql文件导入到新数据库中
---mysql -u [用户名] -p [数据库名] < [拷贝过来的文件名].sql

```

### 3. 运行排课

```powershell
# 检查数据规模并获取推荐参数
python check_data_scale.py

# 运行排课(标准配置)
python suan2.py --version 1 --population 200 --generations 300

# 查看结果(生成Excel文件)
python view_schedule.py 1

# 分析冲突
python analyze_conflicts.py 1
```

---

## 使用指南

### 命令行参数

```powershell
python suan2.py [参数]
```

| 参数                | 说明              | 默认值 | 推荐值     |
| ------------------- | ----------------- | ------ | ---------- |
| `--version`         | 排课版本 ID(必需) | -      | 1, 2, 3... |
| `--population`      | 种群大小          | 100    | 200-300    |
| `--generations`     | 进化代数          | 200    | 300-500    |
| `--crossover-rate`  | 交叉率            | 0.85   | 0.8-0.9    |
| `--mutation-rate`   | 变异率            | 0.15   | 0.1-0.2    |
| `--tournament-size` | 锦标赛大小        | 5      | 5-7        |
| `--elitism-size`    | 精英保留数量      | 15     | 10-20      |
| `--max-stagnation`  | 最大停滞代数      | 60     | 50-80      |

### 典型场景

**场景 1: 快速测试(验证数据)**

```powershell
python suan2.py --version 1 --population 80 --generations 100
```

**场景 2: 标准运行(生产环境)**

```powershell
python suan2.py --version 1 --population 200 --generations 300
```

**场景 3: 高质量优化(时间充足)**

```powershell
python suan2.py --version 1 --population 300 --generations 500 --max-stagnation 80
```

**场景 4: 大规模数据(>200 任务)**

```powershell
python suan2.py --version 1 --population 400 --generations 600
```

---

## 优化策略

### 算法优化重点

#### 1. 教室连续性优化(2025-11-23 更新)

**优化内容**:

- 智能教室选择: 优先为同一教师/班级在同一天选择已使用的教室
- 双维度检查: 同时检查教师和班级的连续课程
- 提高惩罚权重: 从 150 提升到 300

**效果**: 减少师生在不同教室间移动,提高教学效率

#### 2. 教室容量硬约束(2025-11-23 更新)

**优化内容**:

- 容量不足惩罚从 -8000 提升到 -60000
- 作为第二高优先级硬约束(仅次于班级冲突)

**效果**: 确保绝对不会出现教室容量不足的情况

#### 3. 利用率优化

**策略**:

- 目标利用率: 75%-90%
- 非线性惩罚函数
- 优先选择容量匹配的教室

### 参数调优建议

#### 根据数据规模选择参数

| 任务数量 | 种群大小 | 进化代数 | 预计耗时   |
| -------- | -------- | -------- | ---------- |
| < 50     | 80-100   | 100-150  | 1-3 分钟   |
| 50-100   | 150-200  | 200-300  | 3-8 分钟   |
| 100-200  | 200-300  | 300-400  | 8-20 分钟  |
| > 200    | 300-500  | 400-600  | 20-60 分钟 |

#### 根据问题类型调整

**班级冲突严重** → 增加 `--population` 和 `--generations`

**教室利用率低** → 调整代码中 `utilization_waste` 权重

**运行时间过长** → 降低参数或使用 `--max-stagnation 30`

---

## 常见问题

### Q1: 为什么会有班级冲突?

**原因**:

- 种群/代数不足,算法未充分探索
- 数据中班级课程过多,资源不足

**解决**:

```powershell
# 方案1: 提高参数
python suan2.py --version 2 --population 300 --generations 500

# 方案2: 检查数据
python check_data_scale.py
```

参考: `排课问题诊断与解决方案.md` 第一章

### Q2: 教室利用率太低怎么办?

**解决**:

1. 检查教室容量是否与班级规模匹配
2. 增加小型教室(20-40 人)
3. 调整 `genetic_algorithm.py` 中利用率目标区间

参考: `排课问题诊断与解决方案.md` 第三章

### Q3: 运行时间太长?

**解决**:

```powershell
# 快速模式(降低参数)
python suan2.py --version 1 --population 100 --generations 150 --max-stagnation 30
```

参考: `排课问题诊断与解决方案.md` 第八章

### Q4: 如何查看详细的冲突信息?

```powershell
# 命令行分析
python analyze_conflicts.py 1

# Excel查看(四个视角)
python view_schedule.py 1
```

### Q5: 能否手动调整部分课程?

可以,在数据库中直接修改:

```sql
UPDATE schedules
SET classroom_id = 'CR005', week_day = 3, start_slot = 6
WHERE schedule_id = 123;
```

---

## 文档索引

### 📘 核心文档

1. **排课系统说明.md**

   - 系统完整说明
   - 核心逻辑详解
   - 操作步骤
   - 优缺点分析
   - 函数索引

2. **排课问题诊断与解决方案.md**
   - 11 类常见问题诊断
   - 分步骤解决方案
   - SQL 诊断脚本
   - 参数调优指南
   - 紧急救援措施

### 📂 代码文档

**主程序模块**:

- `suan2.py` - 程序入口,参数解析,结果保存
- `genetic_algorithm.py` - 遗传算法核心(1294 行)
  - `create_individual()` - 个体生成
  - `fitness()` - 适应度评估
  - `mutate()` - 变异操作
  - `_select_classroom()` - 智能教室选择
  - `_check_classroom_continuity()` - 连续性检查

**数据与工具**:

- `data_models.py` - 数据结构定义
- `db_connector.py` - 数据库操作
- `view_schedule.py` - Excel 四视角导出
- `analyze_conflicts.py` - 冲突分析
- `check_data_scale.py` - 规模检查与参数推荐

---

## 最近更新

### 2025-11-23

✅ **教室连续性优化**

- 智能教室选择: 优先为同一教师/班级选择已用教室
- 双维度检查: 教师维度 + 班级维度
- 惩罚权重提升: 150 → 300

✅ **容量约束强化**

- 容量不足惩罚: -8000 → -60000
- 提升为第二高优先级硬约束

✅ **Excel 导出增强**

- 新增四维度视角(周期/教师/班级/教室)
- 详细字段展示(容量/人数/性质等)

✅ **文档完善**

- 新增《排课问题诊断与解决方案》
- 更新《排课系统说明》
- 重写 README

---

## 技术支持

### 遇到问题时的检查顺序

1. **查看日志**: `scheduling.log`
2. **检查数据**: `python check_data_scale.py`
3. **分析冲突**: `python analyze_conflicts.py [version]`
4. **查阅文档**: `排课问题诊断与解决方案.md`
5. **调整参数**: 根据文档建议调整

### 调试模式

```python
# 在 suan2.py 中启用详细日志
logging.basicConfig(
    level=logging.DEBUG,  # 改为 DEBUG
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
```

---

## 许可证

本项目采用 MIT 许可证。

---

## 贡献指南

欢迎提交 Issue 和 Pull Request!

**开发建议**:

1. 遵循现有代码风格
2. 为新功能添加注释
3. 更新相关文档
4. 测试后再提交

---

**最后更新**: 2025-11-23  
**版本**: v3.0  
**维护状态**: 活跃维护中
