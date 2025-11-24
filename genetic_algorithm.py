# -*- coding: utf-8 -*-
"""
遗传算法核心模块
实现智能排课的遗传算法
"""

import random
import logging
from typing import List, Dict, Set, Tuple, Optional
from collections import defaultdict
import copy

from data_models import *

logger = logging.getLogger(__name__)


class SchedulingGeneticAlgorithm:
    """排课遗传算法"""

    def __init__(self, data: Dict, config: Dict = None):
        self.data = data

        # 基于默认配置，叠加外部传入的配置，避免覆盖掉 penalty_scores 等字段
        base_config = self._default_config()
        if config:
            for key, value in config.items():
                base_config[key] = value
        self.config = base_config

        # 预处理数据
        self._preprocess_data()

        # 构建查找表
        self._build_lookup_tables()

    def _default_config(self) -> Dict:
        """默认配置

        约束与惩罚说明（硬约束 / 软约束）：

        硬约束（违反会被大幅扣分，相当于不可接受）：
        - teacher_conflict: 教师时间冲突
        - class_conflict: 班级时间冲突
        - classroom_conflict: 教室时间冲突
        - capacity_violation: 教室容量不足
        - blackout_violation: 教师黑名单时间上课
        - feature_violation: 教室不满足课程必须的设施
        - thursday_afternoon: 周四下午（第6节及以后）禁止排课
        - campus_commute: 同一教师一天跨多个校区上课

        软约束（违反会按权重扣分，用来“引导”更优方案）：
        - teacher_preference: 未满足教师偏好时间段
        - classroom_continuity: 连续课程未在同一教室
        - utilization_waste: 教室容量浪费（教室太大、学生太少）
        - student_overload: 单个班级某天课时数过多
        - task_relation: 任务关系约束（当前未实际启用，仅预留）
        - required_night_penalty: 必修/通识课安排在晚上 11-13 节
        - required_weekend_penalty: 必修/通识课安排在周末下午（叠加在 weekend_penalty 之上）
        - elective_prime_time_penalty: 选修课占用“黄金时段”（上午和下午前半段）
        - weekend_penalty: 任何课程安排在周六/周日的基础惩罚
        """
        return {
            "population_size": 100,
            "generations": 200,
            "crossover_rate": 0.85,  # 提高交叉率，增加种群多样性
            "mutation_rate": 0.15,  # 提高变异率，帮助跳出局部最优
            "tournament_size": 5,
            "elitism_size": 15,  # 增加精英保留，保护优秀基因
            "max_stagnation": 60,  # 增加容忍度，给算法更多探索机会
            "penalty_scores": {
                "hard_constraint": -99999,
                "teacher_conflict": -50000,  # 大幅提高：教师冲突必须避免
                "class_conflict": -80000,  # 最高优先级：班级冲突必须完全避免
                "classroom_conflict": -50000,  # 大幅提高：教室冲突必须避免
                "capacity_violation": -60000,  # 极高惩罚：教室容量不足是硬性约束，必须严格避免
                "blackout_violation": -8000,  # 提高：必须尊重教师禁用时间
                "feature_violation": -8000,  # 提高：必须满足设施要求
                "thursday_afternoon": -3000,  # 周四下午软约束
                "campus_commute": -5000,  # 校区通勤保持硬约束
                "teacher_preference": 100,  # 适度调整：平衡教师偏好
                "classroom_continuity": 300,  # 大幅提高：强烈鼓励同教室连续上课
                "utilization_waste": 200,  # 大幅提高：强制提高教室利用率
                "student_overload": 150,  # 适度调整：避免学生过载
                "task_relation": 300,  # 保持：重视课程关系
                "required_night_penalty": 400,  # 保持：必修课避免晚上
                "required_weekend_penalty": 300,  # 保持：必修课避免周末
                "elective_prime_time_penalty": 30,  # 保持：选修课灵活性
                "weekend_penalty": -10000,  # 保持：禁止周末排课
            },
        }

    def _preprocess_data(self):
        """预处理数据"""
        logger.info("开始预处理数据")

        # 按优先级排序教学任务
        self.tasks = self._sort_tasks_by_priority()
        self.task_dict = {task.task_id: task for task in self.tasks}

        # 构建可用教室列表（按容量排序）
        self.classrooms = list(self.data["classrooms"].values())
        self.classrooms.sort(key=lambda x: x.capacity)

        # 构建教师黑名单时间映射
        self.teacher_blackouts = self._build_teacher_blackouts()

        # 构建教师偏好映射
        self.teacher_preferences = self._build_teacher_preferences()

        logger.info(
            f"预处理完成：{len(self.tasks)}个任务，{len(self.classrooms)}个教室"
        )

    def _sort_tasks_by_priority(self) -> List[TeachingTask]:
        """按优先级排序教学任务"""
        tasks = self.data["teaching_tasks"]

        def priority_key(task):
            offering = task.offering
            if not offering:
                return (2, 0, 0, 0)  # 默认优先级

            # 课程性质优先级
            nature_priority = {
                CourseNature.GENERAL: 0,  # 通识最高
                CourseNature.REQUIRED: 1,  # 必修中等
                CourseNature.ELECTIVE: 2,  # 选修最低
            }

            # 课时长度优先级（越长的课程越优先，避免时间块被短课程占用）
            slots_priority = -task.slots_count  # 负号表示降序，4节>3节>2节

            # 学生人数（越多优先级越高）
            student_count = task.student_count or 0

            # 计算该offering的总学时
            offering_tasks = [t for t in tasks if t.offering_id == task.offering_id]
            total_slots = sum(t.slots_count for t in offering_tasks)

            return (
                nature_priority.get(offering.course_nature, 2),
                slots_priority,  # 课时长度优先级（新增）
                -student_count,  # 负号表示降序
                -total_slots,  # 负号表示降序
            )

        sorted_tasks = sorted(tasks, key=priority_key)
        logger.info("任务优先级排序完成：长课程优先，必修课优先")
        return sorted_tasks

    def _build_teacher_blackouts(self) -> Dict[str, Set[Tuple[int, int]]]:
        """构建教师黑名单时间映射"""
        blackouts = defaultdict(set)
        for blackout in self.data["teacher_blackout_times"]:
            teacher_id = blackout.teacher_id
            for slot in range(blackout.start_slot, blackout.end_slot + 1):
                blackouts[teacher_id].add((blackout.weekday, slot))
        return dict(blackouts)

    def _build_teacher_preferences(self) -> Dict[str, Dict]:
        """构建教师偏好映射"""
        preferences = defaultdict(lambda: {"preferred": [], "avoided": []})

        for pref in self.data["teacher_preferences"]:
            teacher_id = pref.teacher_id
            if pref.weekday and pref.start_slot and pref.end_slot:
                time_range = (pref.weekday, pref.start_slot, pref.end_slot)
                if pref.preference_type == PreferenceType.PREFERRED:
                    preferences[teacher_id]["preferred"].append(
                        (time_range, pref.penalty_score)
                    )
                else:
                    preferences[teacher_id]["avoided"].append(
                        (time_range, pref.penalty_score)
                    )

        return dict(preferences)

    def _build_lookup_tables(self):
        """构建查找表提高性能"""
        # 按校区分组教室
        self.classrooms_by_campus = defaultdict(list)
        for classroom in self.classrooms:
            self.classrooms_by_campus[classroom.campus_id].append(classroom)

        # 按特征分组教室
        self.classrooms_by_feature = defaultdict(list)
        for classroom in self.classrooms:
            for feature in classroom.features:
                self.classrooms_by_feature[feature].append(classroom)

    def create_individual(self) -> List[Gene]:
        """创建一个个体（染色体）"""
        genes = []

        # 跟踪占用情况
        teacher_schedule = defaultdict(set)  # teacher_id -> {(weekday, slot), ...}
        class_schedule = defaultdict(set)  # class_id -> {(weekday, slot), ...}
        classroom_schedule = defaultdict(set)  # classroom_id -> {(weekday, slot), ...}

        for task in self.tasks:
            gene = self._create_gene_for_task(
                task, teacher_schedule, class_schedule, classroom_schedule
            )
            if gene:
                genes.append(gene)
                self._update_schedules(
                    gene, task, teacher_schedule, class_schedule, classroom_schedule
                )

        return genes

    def _create_gene_for_task(
        self,
        task: TeachingTask,
        teacher_schedule: Dict,
        class_schedule: Dict,
        classroom_schedule: Dict,
    ) -> Optional[Gene]:
        """为单个任务创建基因"""
        if not task.teachers:
            return None

        # 获取有效时间块
        valid_slots = get_valid_time_slots(task.slots_count)

        # 根据课程性质确定时间偏好
        preferred_weekdays = self._get_preferred_weekdays(task)
        preferred_time_slots = self._get_preferred_time_slots(task, valid_slots)

        # 尝试多次找到可行的安排
        max_attempts = 300  # 大幅增加尝试次数以减少班级冲突

        # 首先尝试偏好时间（60%的尝试）
        for attempt in range(int(max_attempts * 0.6)):
            # 随机选择教师
            teacher_id = random.choice(task.teachers)

            # 优先选择偏好的时间
            weekday = random.choice(preferred_weekdays)
            start_slot, _ = random.choice(preferred_time_slots)

            # 检查周四下午限制
            if weekday == 4 and start_slot >= 6:  # 周四下午
                continue

            # 检查教师黑名单时间
            if self._violates_teacher_blackout(
                teacher_id, weekday, start_slot, task.slots_count
            ):
                continue

            # 检查时间冲突
            if self._has_time_conflict(
                teacher_id,
                task.classes,
                weekday,
                start_slot,
                task.slots_count,
                teacher_schedule,
                class_schedule,
                task_id=task.task_id,
            ):
                continue

            # 选择合适的教室（优化：传入上下文以提高连续性）
            classroom = self._select_classroom(
                task,
                weekday,
                start_slot,
                classroom_schedule,
                teacher_id=teacher_id,
                class_ids=task.classes,
                existing_genes=[],  # 初始创建时无已有基因
            )
            if classroom:
                return Gene(
                    task.task_id,
                    teacher_id,
                    classroom.classroom_id,
                    weekday,
                    start_slot,
                )

        # 如果偏好时间无法安排，尝试所有可能时间（40%的尝试）
        for attempt in range(int(max_attempts * 0.4)):
            # 随机选择教师
            teacher_id = random.choice(task.teachers)

            # 随机选择时间（只选工作日，避免周末硬约束）
            weekday = random.randint(1, 5)  # 只选周一到周五
            start_slot, _ = random.choice(valid_slots)

            # 检查周四下午限制
            if weekday == 4 and start_slot >= 6:  # 周四下午
                continue

            # 检查教师黑名单时间
            if self._violates_teacher_blackout(
                teacher_id, weekday, start_slot, task.slots_count
            ):
                continue

            # 检查时间冲突
            if self._has_time_conflict(
                teacher_id,
                task.classes,
                weekday,
                start_slot,
                task.slots_count,
                teacher_schedule,
                class_schedule,
                task_id=task.task_id,
            ):
                continue

            # 选择合适的教室（优化：传入上下文以提高连续性）
            classroom = self._select_classroom(
                task,
                weekday,
                start_slot,
                classroom_schedule,
                teacher_id=teacher_id,
                class_ids=task.classes,
                existing_genes=[],  # 初始创建时无已有基因
            )
            if classroom:
                return Gene(
                    task.task_id,
                    teacher_id,
                    classroom.classroom_id,
                    weekday,
                    start_slot,
                )

        # 如果无法找到可行安排，返回一个随机安排（会在适应度函数中被惩罚）
        teacher_id = random.choice(task.teachers)
        weekday = random.choice(preferred_weekdays)
        start_slot, _ = random.choice(preferred_time_slots)
        classroom = random.choice(self.classrooms)

        return Gene(
            task.task_id, teacher_id, classroom.classroom_id, weekday, start_slot
        )

    def _get_preferred_weekdays(self, task: TeachingTask) -> List[int]:
        """根据课程性质获取偏好的星期"""
        offering = task.offering
        if not offering:
            return list(range(1, 6))  # 默认工作日

        # 所有课程都只安排在工作日（周一到周五）
        # 避免周末排课以符合学生作息习惯
        return list(range(1, 6))  # 周一到周五

    def _get_preferred_time_slots(
        self, task: TeachingTask, valid_slots: List[tuple]
    ) -> List[tuple]:
        """根据课程性质获取偏好的时间段"""
        offering = task.offering
        if not offering:
            return valid_slots

        # 白天时间块（不包括晚上11-13节）
        daytime_slots = [slot for slot in valid_slots if slot[0] <= 10]

        # 必修课和通识课优先安排在白天
        if offering.course_nature in [CourseNature.REQUIRED, CourseNature.GENERAL]:
            if daytime_slots:
                return daytime_slots
            else:
                return valid_slots  # 如果没有白天时间块，使用所有时间块
        else:
            # 选修课可以安排在任何时间
            return valid_slots

    def _violates_teacher_blackout(
        self, teacher_id: str, weekday: int, start_slot: int, slots_count: int
    ) -> bool:
        """检查是否违反教师黑名单时间"""
        blackouts = self.teacher_blackouts.get(teacher_id, set())
        for slot in range(start_slot, start_slot + slots_count):
            if (weekday, slot) in blackouts:
                return True
        return False

    def _has_time_conflict(
        self,
        teacher_id: str,
        class_ids: List[str],
        weekday: int,
        start_slot: int,
        slots_count: int,
        teacher_schedule: Dict,
        class_schedule: Dict,
        task_id: str = None,
    ) -> bool:
        """检查时间冲突

        重要修复: 对于多教师课程,需要检查该任务的所有教师是否有冲突,
        而不仅仅检查基因中被选中的那个教师。
        """
        time_slots = {
            (weekday, slot) for slot in range(start_slot, start_slot + slots_count)
        }

        # 如果提供了task_id,检查该任务的所有教师
        if task_id and task_id in self.task_dict:
            task = self.task_dict[task_id]
            for tid in task.teachers:
                if teacher_schedule[tid] & time_slots:
                    return True
        else:
            # 向后兼容:只检查传入的单个教师
            if teacher_schedule[teacher_id] & time_slots:
                return True

        # 检查班级冲突
        for class_id in class_ids:
            if class_schedule[class_id] & time_slots:
                return True

        return False

    def _select_classroom(
        self,
        task: TeachingTask,
        weekday: int,
        start_slot: int,
        classroom_schedule: Dict,
        teacher_id: str = None,
        class_ids: List[str] = None,
        existing_genes: List[Gene] = None,
    ) -> Optional[Classroom]:
        """选择合适的教室（优化版：优先选择同教师/班级已使用的教室）"""
        time_slots = {
            (weekday, slot) for slot in range(start_slot, start_slot + task.slots_count)
        }

        # 筛选满足容量和特征要求的教室
        suitable_classrooms = []
        for classroom in self.classrooms:
            # 检查容量
            if classroom.capacity < task.student_count:
                continue

            # 检查特征要求
            if not task.required_features.issubset(classroom.features):
                continue

            # 检查时间冲突
            if classroom_schedule[classroom.classroom_id] & time_slots:
                continue

            suitable_classrooms.append(classroom)

        if suitable_classrooms:
            # 优先选择同教师/班级在当天已使用的教室（提高连续性）
            preferred_classrooms = []
            if existing_genes and (teacher_id or class_ids):
                used_classrooms_today = set()
                for gene in existing_genes:
                    if gene.week_day == weekday:
                        # 同教师
                        if teacher_id and gene.teacher_id == teacher_id:
                            used_classrooms_today.add(gene.classroom_id)
                        # 同班级
                        if class_ids:
                            gene_task = self.task_dict.get(gene.task_id)
                            if gene_task and set(gene_task.classes) & set(class_ids):
                                used_classrooms_today.add(gene.classroom_id)

                # 筛选出已使用的教室
                for classroom in suitable_classrooms:
                    if classroom.classroom_id in used_classrooms_today:
                        preferred_classrooms.append(classroom)

            # 优先使用已使用的教室，如果没有则使用所有合适教室
            classrooms_to_choose = (
                preferred_classrooms if preferred_classrooms else suitable_classrooms
            )

            # 优先选择容量最匹配的教室（提高利用率）
            # 目标：利用率在75%-90%之间最佳
            def utilization_score(classroom):
                """计算教室利用率得分，越接近理想利用率得分越高"""
                if classroom.capacity == 0:
                    return float("inf")

                utilization = task.student_count / classroom.capacity

                # 如果是优先教室（已使用），给予额外奖励
                is_preferred = classroom.classroom_id in (
                    {c.classroom_id for c in preferred_classrooms}
                    if preferred_classrooms
                    else set()
                )
                preference_bonus = -0.2 if is_preferred else 0  # 负数表示更优先

                # 理想利用率：75%-90%
                if 0.75 <= utilization <= 0.90:
                    return (
                        abs(0.825 - utilization) + preference_bonus
                    )  # 最接近82.5%的最好
                elif 0.60 <= utilization < 0.75:
                    return 0.15 + abs(0.675 - utilization) + preference_bonus  # 次优
                elif 0.90 < utilization <= 1.0:
                    return 0.10 + abs(0.95 - utilization) + preference_bonus  # 可接受
                else:
                    # 利用率太低或超过容量，惩罚很大
                    return 1.0 + abs(0.80 - utilization) + preference_bonus

            classrooms_to_choose.sort(key=utilization_score)
            return classrooms_to_choose[0]

        return None

    def _update_schedules(
        self,
        gene: Gene,
        task: TeachingTask,
        teacher_schedule: Dict,
        class_schedule: Dict,
        classroom_schedule: Dict,
    ):
        """更新时间占用情况

        重要修复: 对于多教师课程,需要标记所有教师的时间占用,
        而不是只标记基因中选中的那个教师。
        """
        time_slots = {
            (gene.week_day, slot)
            for slot in range(gene.start_slot, gene.start_slot + task.slots_count)
        }

        # 修复: 更新任务的所有教师的时间占用
        for teacher_id in task.teachers:
            teacher_schedule[teacher_id].update(time_slots)

        classroom_schedule[gene.classroom_id].update(time_slots)

        for class_id in task.classes:
            class_schedule[class_id].update(time_slots)

    def fitness(self, individual: List[Gene]) -> float:
        """计算适应度函数

        总体策略：
        1. 先计算硬约束惩罚（_check_hard_constraints）：只要出现严重冲突，分数会非常低；
        2. 如果硬约束分数低于阈值（例如大量冲突），直接返回，避免浪费时间；
        3. 在硬约束基础上再叠加软约束惩罚（_check_soft_constraints），用于微调解。
        """
        score = 0

        # 构建时间占用表
        teacher_schedule = defaultdict(list)
        class_schedule = defaultdict(list)
        classroom_schedule = defaultdict(list)

        for gene in individual:
            task = self.task_dict[gene.task_id]
            end_slot = gene.start_slot + task.slots_count - 1

            for slot in range(gene.start_slot, end_slot + 1):
                time_key = (gene.week_day, slot)

                # 修复: 记录任务的所有教师的时间占用
                for teacher_id in task.teachers:
                    teacher_schedule[teacher_id].append(time_key)

                classroom_schedule[gene.classroom_id].append(time_key)

                for class_id in task.classes:
                    class_schedule[class_id].append(time_key)

        # 检查硬约束
        score += self._check_hard_constraints(
            individual, teacher_schedule, class_schedule, classroom_schedule
        )

        # 如果硬约束被违反，直接返回低分
        if score < -50000:
            return score

        # 检查软约束
        score -= self._check_soft_constraints(
            individual, teacher_schedule, class_schedule, classroom_schedule
        )

        return score

    def _check_hard_constraints(
        self,
        individual: List[Gene],
        teacher_schedule: Dict,
        class_schedule: Dict,
        classroom_schedule: Dict,
    ) -> float:
        """检查硬约束

        对应的硬约束包括：
        - 教师时间冲突（teacher_conflict）
        - 班级时间冲突（class_conflict）
        - 教室时间冲突（classroom_conflict）
        - 教室容量不足（capacity_violation）
        - 教室设施不满足必需特征（feature_violation）
        - 教师黑名单时间上课（blackout_violation）
        - 周四下午上课（thursday_afternoon）
        - 教师一天跨多个校区上课（campus_commute）
        """
        penalty = 0

        # 检查时间冲突（教师 / 班级 / 教室 三类硬约束）
        for schedule_dict, conflict_type in [
            (teacher_schedule, "teacher_conflict"),
            (class_schedule, "class_conflict"),
            (classroom_schedule, "classroom_conflict"),
        ]:
            for entity_id, time_list in schedule_dict.items():
                if len(time_list) != len(set(time_list)):
                    penalty += self.config["penalty_scores"][conflict_type]

        # 检查其他硬约束：容量、设施、黑名单、周四下午、校区通勤
        for gene in individual:
            task = self.task_dict[gene.task_id]

            # 检查教室容量
            classroom = self.data["classrooms"][gene.classroom_id]
            if classroom.capacity < task.student_count:
                penalty += self.config["penalty_scores"]["capacity_violation"]

            # 检查特征要求
            if not task.required_features.issubset(classroom.features):
                penalty += self.config["penalty_scores"]["feature_violation"]

            # 检查教师黑名单时间
            if self._violates_teacher_blackout(
                gene.teacher_id, gene.week_day, gene.start_slot, task.slots_count
            ):
                penalty += self.config["penalty_scores"]["blackout_violation"]

            # 检查周四下午限制
            if gene.week_day == 4 and gene.start_slot >= 6:
                penalty += self.config["penalty_scores"]["thursday_afternoon"]

        # 检查校区通勤（现在视为硬约束）：同一教师同一天涉及多个校区
        teacher_daily_campuses = defaultdict(lambda: defaultdict(set))

        for gene in individual:
            classroom = self.data["classrooms"][gene.classroom_id]
            campus_id = classroom.campus_id

            # 判断时段（上午：1-5，下午：6-10，晚上：11-13）
            if gene.start_slot <= 5:
                period = "morning"
            elif gene.start_slot <= 10:
                period = "afternoon"
            else:
                period = "evening"

            teacher_daily_campuses[gene.teacher_id][gene.week_day].add(
                (period, campus_id)
            )

        for teacher_id, daily_campuses in teacher_daily_campuses.items():
            for weekday, period_campuses in daily_campuses.items():
                campuses = {campus_id for _, campus_id in period_campuses}
                if len(campuses) > 1:
                    penalty += self.config["penalty_scores"]["campus_commute"]

        return penalty

    def _check_soft_constraints(
        self,
        individual: List[Gene],
        teacher_schedule: Dict,
        class_schedule: Dict,
        classroom_schedule: Dict,
    ) -> float:
        """检查软约束

        对应的软约束包括：
        - 教师时间偏好（_check_teacher_preferences）
        - 连续课程是否在同一教室（_check_classroom_continuity）
        - 教室容量利用率（_check_utilization_waste）
        - 学生每日课时负荷（_check_student_overload）
        - 课程时段偏好与周末惩罚（_check_course_time_preference）
        """
        penalty = 0

        # 教师偏好
        penalty += self._check_teacher_preferences(individual)

        # 连堂课同教室
        penalty += self._check_classroom_continuity(individual)

        # 教室利用率
        penalty += self._check_utilization_waste(individual)

        # 学生负荷
        penalty += self._check_student_overload(class_schedule)

        # 课程时段偏好（新增）
        penalty += self._check_course_time_preference(individual)

        return penalty

    def _check_teacher_preferences(self, individual: List[Gene]) -> float:
        """检查教师偏好（软约束）

        - 对教师声明为“避免”的时间段，若课程落入其中，则按照配置中的 penalty_score 直接扣分；
        - 如果教师声明了“偏好”时间段，而课程完全不在这些偏好块内，则额外扣一次 teacher_preference。
        """
        penalty = 0

        for gene in individual:
            task = self.task_dict[gene.task_id]
            teacher_prefs = self.teacher_preferences.get(gene.teacher_id, {})

            # 检查避免时段
            for (weekday, start_slot, end_slot), penalty_score in teacher_prefs.get(
                "avoided", []
            ):
                if gene.week_day == weekday and not (
                    gene.start_slot + task.slots_count <= start_slot
                    or gene.start_slot >= end_slot + 1
                ):
                    penalty += penalty_score

            # 检查偏好时段
            in_preferred = False
            for (weekday, start_slot, end_slot), penalty_score in teacher_prefs.get(
                "preferred", []
            ):
                if (
                    gene.week_day == weekday
                    and gene.start_slot >= start_slot
                    and gene.start_slot + task.slots_count <= end_slot + 1
                ):
                    in_preferred = True
                    break

            if not in_preferred and teacher_prefs.get("preferred"):
                penalty += self.config["penalty_scores"]["teacher_preference"]

        return penalty

    def _check_campus_commute(self, individual: List[Gene]) -> float:
        """检查校区通勤（软约束）

        - 按教师 + 日期统计当天涉及的校区数量；
        - 如果同一天涉及多个校区，则按 (校区数 - 1) * campus_commute 扣分，鼓励同一教师当天尽量固定在一个校区。
        """
        penalty = 0

        # 按教师和日期分组
        teacher_daily_campuses = defaultdict(lambda: defaultdict(set))

        for gene in individual:
            classroom = self.data["classrooms"][gene.classroom_id]
            campus_id = classroom.campus_id

            # 判断时段（上午：1-5，下午：6-10，晚上：11-13）
            if gene.start_slot <= 5:
                period = "morning"
            elif gene.start_slot <= 10:
                period = "afternoon"
            else:
                period = "evening"

            teacher_daily_campuses[gene.teacher_id][gene.week_day].add(
                (period, campus_id)
            )

        # 检查每个教师每天的校区数量
        for teacher_id, daily_campuses in teacher_daily_campuses.items():
            for weekday, period_campuses in daily_campuses.items():
                # 提取所有校区
                campuses = set()
                for period, campus_id in period_campuses:
                    campuses.add(campus_id)

                if len(campuses) > 1:
                    penalty += self.config["penalty_scores"]["campus_commute"] * (
                        len(campuses) - 1
                    )

        return penalty

    def _check_classroom_continuity(self, individual: List[Gene]) -> float:
        """检查连堂课同教室（软约束）- 增强版

        优化目标：
        1. 同一教师在同一天的连续课程应在同一教室
        2. 同一班级在同一天的连续课程应在同一教室
        """
        penalty = 0

        # 按教师和日期分组
        teacher_daily_classes = defaultdict(lambda: defaultdict(list))
        # 按班级和日期分组
        class_daily_classes = defaultdict(lambda: defaultdict(list))

        for gene in individual:
            task = self.task_dict[gene.task_id]

            # 教师维度
            teacher_daily_classes[gene.teacher_id][gene.week_day].append(
                (
                    gene.start_slot,
                    gene.start_slot + task.slots_count - 1,
                    gene.classroom_id,
                )
            )

            # 班级维度
            for class_id in task.classes:
                class_daily_classes[class_id][gene.week_day].append(
                    (
                        gene.start_slot,
                        gene.start_slot + task.slots_count - 1,
                        gene.classroom_id,
                    )
                )

        # 检查教师连续课程
        for teacher_id, daily_classes in teacher_daily_classes.items():
            for weekday, classes in daily_classes.items():
                classes.sort(key=lambda x: x[0])  # 按开始时间排序

                for i in range(len(classes) - 1):
                    curr_end = classes[i][1]
                    next_start = classes[i + 1][0]
                    curr_classroom = classes[i][2]
                    next_classroom = classes[i + 1][2]

                    # 如果是连续课程但不在同一教室
                    if curr_end + 1 == next_start and curr_classroom != next_classroom:
                        penalty += self.config["penalty_scores"]["classroom_continuity"]

        # 检查班级连续课程
        for class_id, daily_classes in class_daily_classes.items():
            for weekday, classes in daily_classes.items():
                classes.sort(key=lambda x: x[0])

                for i in range(len(classes) - 1):
                    curr_end = classes[i][1]
                    next_start = classes[i + 1][0]
                    curr_classroom = classes[i][2]
                    next_classroom = classes[i + 1][2]

                    # 如果是连续课程但不在同一教室
                    if curr_end + 1 == next_start and curr_classroom != next_classroom:
                        penalty += (
                            self.config["penalty_scores"]["classroom_continuity"] * 0.8
                        )  # 班级权重略低

        return penalty

    def _check_utilization_waste(self, individual: List[Gene]) -> float:
        """检查教室利用率（软约束）

        - 对于每一门课，计算教室容量 - 学生人数，如果有“空位”，乘以 utilization_waste 扣分；
        - 鼓励把大班放到大教室，小班放到小教室，提高利用率。
        """
        penalty = 0

        for gene in individual:
            task = self.task_dict[gene.task_id]
            classroom = self.data["classrooms"][gene.classroom_id]

            if classroom.capacity == 0:
                continue

            utilization = task.student_count / classroom.capacity

            # 非线性惩罚：鼓励75%-90%的理想利用率
            if 0.75 <= utilization <= 0.90:
                penalty += 0  # 理想范围
            elif 0.60 <= utilization < 0.75:
                penalty += (
                    (0.75 - utilization)
                    * 100
                    * self.config["penalty_scores"]["utilization_waste"]
                )
            elif 0.90 < utilization <= 1.0:
                penalty += (
                    (utilization - 0.90)
                    * 50
                    * self.config["penalty_scores"]["utilization_waste"]
                )
            elif utilization < 0.60:
                waste_ratio = 0.60 - utilization
                penalty += (waste_ratio * waste_ratio * 500) * self.config[
                    "penalty_scores"
                ]["utilization_waste"]

        return penalty

    def _check_student_overload(self, class_schedule: Dict) -> float:
        """检查学生负荷（软约束）

        - 按班级 + 日期统计一天的总节数；
        - 超过 8 节的部分，每多 1 节，按 student_overload 扣分，
          防止学生某一天课太多、过于疲惫。
        """
        penalty = 0

        for class_id, time_list in class_schedule.items():
            # 按天统计课程数
            daily_count = defaultdict(int)
            for weekday, slot in time_list:
                daily_count[weekday] += 1

            for weekday, count in daily_count.items():
                if count > 8:  # 一天超过8节课
                    penalty += self.config["penalty_scores"]["student_overload"] * (
                        count - 8
                    )

        return penalty

    def _check_course_time_preference(self, individual: List[Gene]) -> float:
        """检查课程时段偏好与周末惩罚（软约束）

        - weekend_penalty: 所有课程在周六/周日都会被扣一次基础分；
        - required_night_penalty: 必修 / 通识课如果安排在晚上 11-13 节，额外扣分；
        - required_weekend_penalty: 必修 / 通识课在周末下午（6 节以后）再叠加一次惩罚；
        - elective_prime_time_penalty: 选修课如果占用上午或下午前半段（黄金时段），会有轻微惩罚。
        """
        penalty = 0

        for gene in individual:
            task = self.task_dict[gene.task_id]
            offering = task.offering

            if not offering:
                continue

            # 周末通用惩罚：任何课程安排在周六/周日都会有基础惩罚
            if gene.week_day in [6, 7]:
                penalty += self.config["penalty_scores"]["weekend_penalty"]

            # 检查必修课和通识课是否被安排在晚上（11-13节）
            if offering.course_nature in [CourseNature.REQUIRED, CourseNature.GENERAL]:
                if gene.start_slot >= 11:  # 晚上时段
                    # 必修课在晚上的惩罚比较重
                    penalty += self.config["penalty_scores"]["required_night_penalty"]
                elif gene.start_slot >= 6 and gene.week_day in [6, 7]:  # 周末下午
                    # 必修课在周末的额外惩罚（在通用周末惩罚基础上再叠加）
                    penalty += self.config["penalty_scores"]["required_weekend_penalty"]

            # 检查选修课是否过度占用黄金时段（上午和下午前半段）
            elif offering.course_nature == CourseNature.ELECTIVE:
                if gene.start_slot <= 5 or (
                    gene.start_slot >= 6 and gene.start_slot <= 8
                ):
                    # 选修课占用黄金时段的轻微惩罚
                    penalty += self.config["penalty_scores"][
                        "elective_prime_time_penalty"
                    ]

        return penalty

    def crossover(
        self, parent1: List[Gene], parent2: List[Gene]
    ) -> Tuple[List[Gene], List[Gene]]:
        """交叉操作"""
        if random.random() > self.config["crossover_rate"]:
            return parent1[:], parent2[:]

        # 单点交叉
        crossover_point = random.randint(1, min(len(parent1), len(parent2)) - 1)

        child1 = parent1[:crossover_point] + parent2[crossover_point:]
        child2 = parent2[:crossover_point] + parent1[crossover_point:]

        return child1, child2

    def mutate(self, individual: List[Gene]) -> List[Gene]:
        """变异操作（增强版，带冲突修复）"""
        mutated = individual[:]

        for i, gene in enumerate(mutated):
            if random.random() < self.config["mutation_rate"]:
                # 调整变异类型权重：增加智能修复的概率
                mutation_types = [
                    "teacher",
                    "time",
                    "classroom",
                    "smart_repair",
                    "smart_repair",
                    "smart_repair",
                ]
                mutation_type = random.choice(mutation_types)

                task = self.task_dict[gene.task_id]

                if mutation_type == "teacher" and len(task.teachers) > 1:
                    # 更换教师
                    new_teacher = random.choice(
                        [t for t in task.teachers if t != gene.teacher_id]
                    )
                    mutated[i] = Gene(
                        gene.task_id,
                        new_teacher,
                        gene.classroom_id,
                        gene.week_day,
                        gene.start_slot,
                    )

                elif mutation_type == "time":
                    # 更换时间（避开周末）
                    valid_slots = get_valid_time_slots(task.slots_count)
                    new_weekday = random.randint(1, 5)  # 只选工作日
                    new_start_slot, _ = random.choice(valid_slots)

                    # 避开周四下午
                    if new_weekday == 4 and new_start_slot >= 6:
                        new_start_slot = random.choice(
                            [s for s, _ in valid_slots if s < 6]
                        )

                    mutated[i] = Gene(
                        gene.task_id,
                        gene.teacher_id,
                        gene.classroom_id,
                        new_weekday,
                        new_start_slot,
                    )

                elif mutation_type == "classroom":
                    # 更换教室（优先选择容量匹配的）
                    suitable_classrooms = [
                        cr
                        for cr in self.classrooms
                        if (
                            cr.capacity >= task.student_count
                            and task.required_features.issubset(cr.features)
                        )
                    ]
                    if suitable_classrooms:
                        # 按容量接近程度排序
                        suitable_classrooms.sort(
                            key=lambda x: abs(x.capacity - task.student_count * 1.2)
                        )
                        # 有70%概率选最佳，30%随机选择
                        if random.random() < 0.7:
                            new_classroom = suitable_classrooms[0]
                        else:
                            new_classroom = random.choice(
                                suitable_classrooms[:5]
                                if len(suitable_classrooms) > 5
                                else suitable_classrooms
                            )

                        mutated[i] = Gene(
                            gene.task_id,
                            gene.teacher_id,
                            new_classroom.classroom_id,
                            gene.week_day,
                            gene.start_slot,
                        )

                elif mutation_type == "smart_repair":
                    # 智能修复：检测冲突并尝试解决
                    mutated[i] = self._repair_conflicting_gene(
                        gene, mutated[:i] + mutated[i + 1 :], task
                    )

        return mutated

    def _repair_conflicting_gene(
        self, gene: Gene, other_genes: List[Gene], task: TeachingTask
    ) -> Gene:
        """修复有冲突的基因 - 增强版，优先解决班级冲突"""
        # 检查当前基因是否有冲突，并记录冲突类型
        has_class_conflict = False
        has_teacher_conflict = False
        has_classroom_conflict = False

        for other_gene in other_genes:
            if (
                other_gene.week_day == gene.week_day
                and other_gene.start_slot == gene.start_slot
            ):
                other_task = self.task_dict[other_gene.task_id]

                # 检查班级冲突（最高优先级）
                if set(task.classes) & set(other_task.classes):
                    has_class_conflict = True

                # 检查教师冲突
                if gene.teacher_id == other_gene.teacher_id:
                    has_teacher_conflict = True

                # 检查教室冲突
                if gene.classroom_id == other_gene.classroom_id:
                    has_classroom_conflict = True

        if not (has_class_conflict or has_teacher_conflict or has_classroom_conflict):
            return gene  # 无冲突，不需要修复

        # 尝试找到无冲突的时间
        valid_slots = get_valid_time_slots(task.slots_count)
        attempts = 0
        max_attempts = 50  # 增加尝试次数

        # 如果有班级冲突，使用更激进的策略
        if has_class_conflict:
            max_attempts = 80  # 班级冲突更多尝试

        while attempts < max_attempts:
            new_weekday = random.randint(1, 5)  # 工作日
            new_start_slot, _ = random.choice(valid_slots)

            # 避开周四下午
            if new_weekday == 4 and new_start_slot >= 6:
                attempts += 1
                continue

            # 检查新时间是否有冲突
            new_has_class_conflict = False
            new_has_teacher_conflict = False
            new_has_classroom_conflict = False

            for other_gene in other_genes:
                if (
                    other_gene.week_day == new_weekday
                    and other_gene.start_slot == new_start_slot
                ):
                    other_task = self.task_dict[other_gene.task_id]

                    # 优先检查班级冲突
                    if set(task.classes) & set(other_task.classes):
                        new_has_class_conflict = True
                        break  # 立即退出，重新尝试

                    if gene.teacher_id == other_gene.teacher_id:
                        new_has_teacher_conflict = True

                    if gene.classroom_id == other_gene.classroom_id:
                        new_has_classroom_conflict = True

            # 无任何冲突才接受
            if not (
                new_has_class_conflict
                or new_has_teacher_conflict
                or new_has_classroom_conflict
            ):
                # 找到无冲突时间
                return Gene(
                    gene.task_id,
                    gene.teacher_id,
                    gene.classroom_id,
                    new_weekday,
                    new_start_slot,
                )

            attempts += 1

        # 如果找不到，返回原基因
        return gene

    def tournament_selection(
        self, population: List[List[Gene]], fitness_scores: List[float]
    ) -> List[Gene]:
        """锦标赛选择"""
        tournament_size = self.config["tournament_size"]
        tournament_indices = random.sample(
            range(len(population)), min(tournament_size, len(population))
        )

        best_idx = max(tournament_indices, key=lambda i: fitness_scores[i])
        return population[best_idx][:]

    def evolve(self) -> List[Gene]:
        """进化主循环"""
        logger.info("开始遗传算法进化")

        # 初始化种群
        population = [
            self.create_individual() for _ in range(self.config["population_size"])
        ]

        best_fitness = float("-inf")
        stagnation_count = 0

        for generation in range(self.config["generations"]):
            # 计算适应度
            fitness_scores = [self.fitness(individual) for individual in population]

            # 记录最佳适应度
            current_best = max(fitness_scores)
            if current_best > best_fitness:
                best_fitness = current_best
                stagnation_count = 0
                logger.info(f"第 {generation} 代，新的最佳适应度: {best_fitness:.2f}")
            else:
                stagnation_count += 1

            # 检查停滞
            if stagnation_count >= self.config["max_stagnation"]:
                logger.info(f"算法停滞 {stagnation_count} 代，提前结束")
                break

            # 精英保留
            elite_indices = sorted(
                range(len(fitness_scores)),
                key=lambda i: fitness_scores[i],
                reverse=True,
            )
            elite_size = self.config["elitism_size"]
            new_population = [population[i][:] for i in elite_indices[:elite_size]]

            # 生成新个体
            while len(new_population) < self.config["population_size"]:
                parent1 = self.tournament_selection(population, fitness_scores)
                parent2 = self.tournament_selection(population, fitness_scores)

                child1, child2 = self.crossover(parent1, parent2)
                child1 = self.mutate(child1)
                child2 = self.mutate(child2)

                new_population.extend([child1, child2])

            # 截断到目标大小
            population = new_population[: self.config["population_size"]]

            if generation % 20 == 0:
                logger.info(
                    f"第 {generation} 代完成，当前最佳适应度: {current_best:.2f}"
                )

        # 返回最佳个体
        final_fitness_scores = [self.fitness(individual) for individual in population]
        best_idx = max(
            range(len(final_fitness_scores)), key=lambda i: final_fitness_scores[i]
        )

        logger.info(f"进化完成，最终最佳适应度: {final_fitness_scores[best_idx]:.2f}")

        # 后处理：专门针对班级冲突的修复
        best_solution = population[best_idx]
        best_solution = self._post_process_class_conflicts(best_solution)

        return best_solution

    def _post_process_class_conflicts(self, individual: List[Gene]) -> List[Gene]:
        """后处理：专门修复班级冲突"""
        logger.info("开始后处理班级冲突...")

        # 检测班级冲突
        class_conflicts = self._detect_class_conflicts(individual)

        if not class_conflicts:
            logger.info("未发现班级冲突，无需后处理")
            return individual

        logger.info(f"检测到 {len(class_conflicts)} 处班级冲突，开始修复...")

        improved = individual[:]
        fixed_count = 0

        for conflict_info in class_conflicts[:20]:  # 处理前20个冲突
            gene_idx = conflict_info["gene_index"]
            gene = improved[gene_idx]
            task = self.task_dict[gene.task_id]

            # 尝试为这个冲突的课程找新时间
            other_genes = improved[:gene_idx] + improved[gene_idx + 1 :]
            repaired_gene = self._repair_conflicting_gene(gene, other_genes, task)

            if repaired_gene != gene:
                improved[gene_idx] = repaired_gene
                fixed_count += 1

        logger.info(f"后处理完成，修复了 {fixed_count} 处班级冲突")
        return improved

    def _detect_class_conflicts(self, individual: List[Gene]) -> List[Dict]:
        """检测班级冲突并返回详细信息"""
        from collections import defaultdict

        class_schedule = defaultdict(list)
        conflicts = []

        for idx, gene in enumerate(individual):
            task = self.task_dict[gene.task_id]

            for slot in range(gene.start_slot, gene.start_slot + task.slots_count):
                time_key = (gene.week_day, slot)

                for class_id in task.classes:
                    class_schedule[class_id].append(
                        {"time": time_key, "gene_index": idx, "task_id": gene.task_id}
                    )

        # 查找冲突
        for class_id, schedule_list in class_schedule.items():
            time_dict = defaultdict(list)
            for item in schedule_list:
                time_dict[item["time"]].append(item)

            for time_key, items in time_dict.items():
                if len(items) > 1:
                    # 发现冲突，选择第一个任务来修复
                    conflicts.append(
                        {
                            "class_id": class_id,
                            "time": time_key,
                            "gene_index": items[0]["gene_index"],
                            "task_id": items[0]["task_id"],
                        }
                    )

        return conflicts
