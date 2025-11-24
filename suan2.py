# -*- coding: utf-8 -*-
"""
智能排课系统主程序
使用遗传算法解决复杂的排课优化问题
"""

import argparse
import logging
import os
import sys
import time
from typing import Dict, List

# 添加当前目录到路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from db_connector import DatabaseConnector, DataLoader
from genetic_algorithm import SchedulingGeneticAlgorithm
from data_models import Gene, ScheduleVersion

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("scheduling.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)

logger = logging.getLogger(__name__)

class SchedulingSystem:
    """排课系统主类"""

    def __init__(self):
        self.db_connector = None
        self.data_loader = None

    def setup_database_connection(self):
        """设置数据库连接"""
        # 从环境变量获取数据库配置
        db_config = {
            "host": os.getenv("DB_HOST", "localhost"),
            "user": os.getenv("DB_USER", "root"),
            "password": os.getenv("DB_PASSWORD", "20051113Da"),
            "database": os.getenv("DB_NAME", "paike2"),
            "charset": "utf8mb4",
        }

        logger.info(f"连接数据库: {db_config['host']}:{db_config['database']}")

        self.db_connector = DatabaseConnector(**db_config)
        self.db_connector.connect()
        self.data_loader = DataLoader(self.db_connector)

    def validate_version(self, version_id: int) -> bool:
        """验证排课版本是否存在且状态正确，不存在则自动创建"""
        query = "SELECT * FROM schedule_versions WHERE version_id = %s"
        result = self.db_connector.execute_query(query, (version_id,))

        if not result:
            logger.error(f"排课版本 {version_id} 不存在")
            return False

        version = result[0]
        if version["status"] != "draft":
            logger.error(
                f"排课版本 {version_id} 状态为 {version['status']}，不是草案状态"
            )
            return False

        logger.info(f"验证版本成功: {version['version_name']} ({version['semester']})")
        return True

    def validate_data_integrity(self, data: Dict) -> bool:
        """验证数据完整性"""
        logger.info("开始验证数据完整性")

        issues = []

        # 检查是否有教学任务
        if not data["teaching_tasks"]:
            issues.append("没有找到教学任务")

        # 检查任务是否有教师
        tasks_without_teachers = [
            task for task in data["teaching_tasks"] if not task.teachers
        ]
        if tasks_without_teachers:
            issues.append(f"有 {len(tasks_without_teachers)} 个任务没有分配教师")

        # 检查任务是否有班级
        tasks_without_classes = [
            task for task in data["teaching_tasks"] if not task.classes
        ]
        if tasks_without_classes:
            issues.append(f"有 {len(tasks_without_classes)} 个任务没有分配班级")

        # 检查是否有可用教室
        if not data["classrooms"]:
            issues.append("没有可用教室")

        # 检查slots_count的有效性
        invalid_slots = [
            task for task in data["teaching_tasks"] if task.slots_count not in [2, 3, 4]
        ]
        if invalid_slots:
            issues.append(f"有 {len(invalid_slots)} 个任务的节数不在有效范围(2,3,4)内")

        # 输出问题
        if issues:
            logger.error("数据完整性检查失败:")
            for issue in issues:
                logger.error(f"  - {issue}")
            return False

        logger.info("数据完整性检查通过")
        logger.info(f"  - 教学任务: {len(data['teaching_tasks'])} 个")
        logger.info(f"  - 教师: {len(data['teachers'])} 人")
        logger.info(f"  - 教室: {len(data['classrooms'])} 间")
        logger.info(f"  - 班级: {len(data['classes'])} 个")

        return True

    def run_scheduling(self, version_id: int, ga_config: Dict = None) -> bool:
        """运行排课算法"""
        try:
            start_time = time.time()

            # 验证版本
            if not self.validate_version(version_id):
                return False

            # 获取学期信息
            version_query = (
                "SELECT semester FROM schedule_versions WHERE version_id = %s"
            )
            version_result = self.db_connector.execute_query(
                version_query, (version_id,)
            )
            semester = version_result[0]["semester"]

            # 加载数据
            logger.info(f"开始加载学期 {semester} 的数据")
            data = self.data_loader.load_all_data(semester)

            # 验证数据完整性
            if not self.validate_data_integrity(data):
                return False

            # 初始化遗传算法
            logger.info("初始化遗传算法")
            ga = SchedulingGeneticAlgorithm(data, ga_config)

            # 运行算法
            logger.info("开始运行遗传算法")
            best_solution = ga.evolve()

            # 保存结果
            logger.info("保存排课结果")
            self.data_loader.save_schedule_results(
                version_id, best_solution, ga.task_dict
            )

            # 生成统计报告
            self._generate_report(version_id, best_solution, ga.task_dict, data)

            end_time = time.time()
            logger.info(f"排课完成，总耗时: {end_time - start_time:.2f} 秒")

            return True

        except Exception as e:
            logger.error(f"排课过程中发生错误: {e}")
            import traceback

            logger.error(traceback.format_exc())
            return False

    def _generate_report(
        self, version_id: int, solution: List[Gene], task_dict: Dict, data: Dict
    ):
        """生成排课统计报告"""
        logger.info("生成排课统计报告")

        total_tasks = len(data["teaching_tasks"])
        scheduled_tasks = len(solution)
        coverage_rate = (scheduled_tasks / total_tasks) * 100 if total_tasks > 0 else 0

        logger.info(
            f"排课覆盖率: {coverage_rate:.1f}% ({scheduled_tasks}/{total_tasks})"
        )

        # 检查硬冲突
        conflicts = self._check_conflicts(solution, task_dict, data)

        total_conflicts = (
            conflicts["teacher_count"]
            + conflicts["class_count"]
            + conflicts["classroom_count"]
        )

        if total_conflicts == 0:
            logger.info("✓ 没有发现硬冲突")
        else:
            logger.warning(f"⚠ 发现 {total_conflicts} 处冲突:")

            if conflicts["teacher_count"] > 0:
                logger.warning(f"  - 教师冲突: {conflicts['teacher_count']} 处")
                self._print_conflict_details(conflicts["teacher_details"], "教师", data)

            if conflicts["class_count"] > 0:
                logger.warning(f"  - 班级冲突: {conflicts['class_count']} 处")
                self._print_conflict_details(conflicts["class_details"], "班级", data)

            if conflicts["classroom_count"] > 0:
                logger.warning(f"  - 教室冲突: {conflicts['classroom_count']} 处")
                self._print_conflict_details(
                    conflicts["classroom_details"], "教室", data
                )

        # 教室利用率统计
        self._analyze_classroom_utilization(solution, task_dict, data)

        # 个性化要求满足情况分析
        self._analyze_preference_satisfaction(solution, task_dict, data)

    def _print_conflict_details(
        self, conflict_details: List[Dict], entity_type: str, data: Dict
    ):
        """打印冲突详细信息"""
        day_names = ["", "周一", "周二", "周三", "周四", "周五", "周六", "周日"]

        for i, conflict in enumerate(conflict_details[:5], 1):  # 只显示前5个冲突
            entity_id = conflict["entity_id"]
            weekday = conflict["weekday"]
            slot = conflict["slot"]

            # 获取实体名称
            if entity_type == "教师":
                entity_name = data["teachers"].get(entity_id, None)
                entity_name_str = entity_name.teacher_name if entity_name else entity_id
            elif entity_type == "班级":
                entity_name = data["classes"].get(entity_id, None)
                entity_name_str = entity_name.class_name if entity_name else entity_id
            else:  # 教室
                entity_name = data["classrooms"].get(entity_id, None)
                entity_name_str = (
                    entity_name.classroom_name if entity_name else entity_id
                )

            logger.warning(
                f"    [{i}] {entity_type}: {entity_name_str}, 时间: {day_names[weekday]} 第{slot}节"
            )

            for j, task_info in enumerate(conflict["tasks"], 1):
                teacher_name = data["teachers"].get(task_info["teacher_id"], None)
                teacher_str = (
                    teacher_name.teacher_name
                    if teacher_name
                    else task_info["teacher_id"]
                )

                classroom_name = data["classrooms"].get(task_info["classroom_id"], None)
                classroom_str = (
                    classroom_name.classroom_name
                    if classroom_name
                    else task_info["classroom_id"]
                )

                logger.warning(
                    f"        课程{j}: {task_info['course_name']} | "
                    f"教师: {teacher_str} | "
                    f"教室: {classroom_str} | "
                    f"时间: {task_info['start_slot']}-{task_info['start_slot']+task_info['slots_count']-1}节"
                )

        if len(conflict_details) > 5:
            logger.warning(
                f"    ... 还有 {len(conflict_details) - 5} 处{entity_type}冲突未显示"
            )

    def _check_conflicts(
        self, solution: List[Gene], task_dict: Dict, data: Dict
    ) -> Dict:
        """检查冲突并返回详细信息"""
        from collections import defaultdict

        teacher_schedule = defaultdict(list)
        class_schedule = defaultdict(list)
        classroom_schedule = defaultdict(list)

        # 用于存储基因信息，方便后续查找
        gene_map = {}

        for gene in solution:
            task = task_dict[gene.task_id]
            end_slot = gene.start_slot + task.slots_count - 1

            gene_map[gene.task_id] = gene

            for slot in range(gene.start_slot, end_slot + 1):
                time_key = (gene.week_day, slot)
                # 修复: 检查任务的所有教师,不仅仅是基因中选中的那个
                for teacher_id in task.teachers:
                    teacher_schedule[teacher_id].append((time_key, gene.task_id))
                classroom_schedule[gene.classroom_id].append((time_key, gene.task_id))

                for class_id in task.classes:
                    class_schedule[class_id].append((time_key, gene.task_id))

        # 检测冲突并记录详细信息
        def find_conflicts(schedule_dict, entity_type):
            """查找冲突详情"""
            conflict_count = 0
            conflict_details = []

            for entity_id, time_list in schedule_dict.items():
                # 按时间分组
                time_dict = defaultdict(list)
                for time_key, task_id in time_list:
                    time_dict[time_key].append(task_id)

                # 找出有冲突的时间点
                for time_key, task_ids in time_dict.items():
                    if len(task_ids) > 1:
                        conflict_count += 1
                        weekday, slot = time_key

                        # 获取冲突任务的详细信息
                        conflict_info = {
                            "entity_id": entity_id,
                            "weekday": weekday,
                            "slot": slot,
                            "tasks": [],
                        }

                        for task_id in task_ids:
                            gene = gene_map[task_id]
                            task = task_dict[task_id]
                            offering = task.offering

                            if offering:
                                course_name = data["courses"].get(
                                    offering.course_id, None
                                )
                                course_name_str = (
                                    course_name.course_name
                                    if course_name
                                    else "未知课程"
                                )
                            else:
                                course_name_str = "未知课程"

                            conflict_info["tasks"].append(
                                {
                                    "task_id": task_id,
                                    "course_name": course_name_str,
                                    "teacher_id": gene.teacher_id,
                                    "classroom_id": gene.classroom_id,
                                    "start_slot": gene.start_slot,
                                    "slots_count": task.slots_count,
                                }
                            )

                        conflict_details.append(conflict_info)

            return conflict_count, conflict_details

        teacher_count, teacher_details = find_conflicts(teacher_schedule, "teacher")
        class_count, class_details = find_conflicts(class_schedule, "class")
        classroom_count, classroom_details = find_conflicts(
            classroom_schedule, "classroom"
        )

        return {
            "teacher_count": teacher_count,
            "teacher_details": teacher_details,
            "class_count": class_count,
            "class_details": class_details,
            "classroom_count": classroom_count,
            "classroom_details": classroom_details,
        }

    def _analyze_classroom_utilization(
        self, solution: List[Gene], task_dict: Dict, data: Dict
    ):
        """分析教室利用率"""
        from collections import defaultdict

        classroom_usage = defaultdict(list)

        for gene in solution:
            task = task_dict[gene.task_id]
            classroom = data["classrooms"][gene.classroom_id]

            utilization = (
                task.student_count / classroom.capacity if classroom.capacity > 0 else 0
            )
            classroom_usage[gene.classroom_id].append(utilization)

        # 计算平均利用率
        total_utilization = 0
        used_classrooms = 0

        for classroom_id, utilizations in classroom_usage.items():
            avg_util = sum(utilizations) / len(utilizations)
            total_utilization += avg_util
            used_classrooms += 1

        if used_classrooms > 0:
            overall_utilization = total_utilization / used_classrooms
            logger.info(f"教室平均利用率: {overall_utilization:.1%}")

        # 找出利用率过低的教室
        low_utilization_classrooms = [
            (classroom_id, sum(utils) / len(utils))
            for classroom_id, utils in classroom_usage.items()
            if sum(utils) / len(utils) < 0.5
        ]

        if low_utilization_classrooms:
            logger.warning(
                f"发现 {len(low_utilization_classrooms)} 间教室利用率过低(<50%)"
            )

    def _analyze_preference_satisfaction(
        self, solution: List[Gene], task_dict: Dict, data: Dict
    ):
        """分析个性化要求满足情况"""
        from collections import defaultdict
        from data_models import PreferenceType

        logger.info("\n【个性化要求满足情况分析】")

        # 统计各类个性化要求
        total_preferences = len(data["teacher_preferences"])
        if total_preferences == 0:
            logger.info("✓ 没有设置个性化要求")
            return

        logger.info(f"总共有 {total_preferences} 条个性化要求")

        # 按教师分组个性化要求
        teacher_prefs = defaultdict(lambda: {"preferred": [], "avoided": []})
        for pref in data["teacher_preferences"]:
            if pref.preference_type == PreferenceType.PREFERRED:
                teacher_prefs[pref.teacher_id]["preferred"].append(pref)
            else:
                teacher_prefs[pref.teacher_id]["avoided"].append(pref)

        # 构建教师实际排课时间
        teacher_schedules = defaultdict(list)
        for gene in solution:
            task = task_dict[gene.task_id]
            # 注意：一个任务可能有多个教师
            for teacher_id in task.teachers:
                start_slot = gene.start_slot
                end_slot = start_slot + task.slots_count - 1
                teacher_schedules[teacher_id].append({
                    "weekday": gene.week_day,
                    "start_slot": start_slot,
                    "end_slot": end_slot,
                    "course_name": data["courses"].get(task.offering.course_id).course_name if task.offering else "未知课程",
                    "task_id": gene.task_id
                })

        # 分析每个教师的个性化要求满足情况
        violated_preferred = []  # 未满足的偏好时间
        violated_avoided = []    # 违反的避免时间

        for teacher_id, prefs in teacher_prefs.items():
            teacher_name = data["teachers"].get(teacher_id)
            teacher_name_str = teacher_name.teacher_name if teacher_name else teacher_id
            schedule = teacher_schedules.get(teacher_id, [])

            # 检查偏好时间（PREFERRED）
            for pref in prefs["preferred"]:
                if pref.weekday and pref.start_slot and pref.end_slot:
                    # 检查是否有课程安排在这个时间段
                    found = False
                    for sch in schedule:
                        if sch["weekday"] == pref.weekday:
                            # 检查时间段是否有交集
                            if not (sch["end_slot"] < pref.start_slot or sch["start_slot"] > pref.end_slot):
                                found = True
                                break
                    
                    if not found:
                        violated_preferred.append({
                            "teacher_id": teacher_id,
                            "teacher_name": teacher_name_str,
                            "weekday": pref.weekday,
                            "start_slot": pref.start_slot,
                            "end_slot": pref.end_slot,
                            "penalty_score": pref.penalty_score
                        })

            # 检查避免时间（AVOIDED）
            for pref in prefs["avoided"]:
                if pref.weekday and pref.start_slot and pref.end_slot:
                    # 检查是否有课程安排在这个时间段
                    for sch in schedule:
                        if sch["weekday"] == pref.weekday:
                            # 检查时间段是否有交集
                            if not (sch["end_slot"] < pref.start_slot or sch["start_slot"] > pref.end_slot):
                                violated_avoided.append({
                                    "teacher_id": teacher_id,
                                    "teacher_name": teacher_name_str,
                                    "weekday": pref.weekday,
                                    "start_slot": pref.start_slot,
                                    "end_slot": pref.end_slot,
                                    "course_name": sch["course_name"],
                                    "course_time": f"{sch['start_slot']}-{sch['end_slot']}节",
                                    "penalty_score": pref.penalty_score
                                })
                                break

        # 输出分析结果
        day_names = ["", "周一", "周二", "周三", "周四", "周五", "周六", "周日"]

        # 偏好时间未满足情况
        if violated_preferred:
            logger.warning(f"\n⚠ 发现 {len(violated_preferred)} 条偏好时间未被满足:")
            for i, item in enumerate(violated_preferred[:10], 1):  # 只显示前10条
                logger.warning(
                    f"  [{i}] 教师: {item['teacher_name']}, "
                    f"偏好时间: {day_names[item['weekday']]} {item['start_slot']}-{item['end_slot']}节, "
                    f"惩罚分数: {item['penalty_score']}"
                )
            if len(violated_preferred) > 10:
                logger.warning(f"  ... 还有 {len(violated_preferred) - 10} 条偏好时间未满足")
        else:
            logger.info("✓ 所有偏好时间都已满足")

        # 避免时间被违反情况
        if violated_avoided:
            logger.warning(f"\n⚠ 发现 {len(violated_avoided)} 条避免时间被违反:")
            for i, item in enumerate(violated_avoided[:10], 1):  # 只显示前10条
                logger.warning(
                    f"  [{i}] 教师: {item['teacher_name']}, "
                    f"避免时间: {day_names[item['weekday']]} {item['start_slot']}-{item['end_slot']}节, "
                    f"实际课程: {item['course_name']} ({item['course_time']}), "
                    f"惩罚分数: {item['penalty_score']}"
                )
            if len(violated_avoided) > 10:
                logger.warning(f"  ... 还有 {len(violated_avoided) - 10} 条避免时间被违反")
        else:
            logger.info("✓ 所有避免时间都已遵守")

        # 计算总体满足率
        total_prefs_count = sum(len(p["preferred"]) + len(p["avoided"]) for p in teacher_prefs.values())
        satisfied_count = total_prefs_count - len(violated_preferred) - len(violated_avoided)
        satisfaction_rate = (satisfied_count / total_prefs_count * 100) if total_prefs_count > 0 else 100

        logger.info(f"\n个性化要求总体满足率: {satisfaction_rate:.1f}% ({satisfied_count}/{total_prefs_count})")

    def cleanup(self):
        """清理资源"""
        if self.db_connector:
            self.db_connector.disconnect()


def parse_arguments():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description="智能排课系统")

    parser.add_argument("--version", type=int, required=True, help="排课版本ID")
    parser.add_argument("--semester", type=str, help="学期（如果不指定则从版本中获取）")
    parser.add_argument(
        "--population", type=int, default=100, help="种群大小 (默认: 100)"
    )
    parser.add_argument(
        "--generations", type=int, default=200, help="进化代数 (默认: 200)"
    )
    parser.add_argument(
        "--crossover-rate", type=float, default=0.8, help="交叉率 (默认: 0.8)"
    )
    parser.add_argument(
        "--mutation-rate", type=float, default=0.1, help="变异率 (默认: 0.1)"
    )
    parser.add_argument(
        "--tournament-size", type=int, default=5, help="锦标赛大小 (默认: 5)"
    )
    parser.add_argument(
        "--elitism-size", type=int, default=10, help="精英个体数量 (默认: 10)"
    )
    parser.add_argument(
        "--max-stagnation", type=int, default=50, help="最大停滞代数 (默认: 50)"
    )

    return parser.parse_args()


def main():
    """主函数"""
    args = parse_arguments()

    # 构建遗传算法配置
    ga_config = {
        "population_size": args.population,
        "generations": args.generations,
        "crossover_rate": args.crossover_rate,
        "mutation_rate": args.mutation_rate,
        "tournament_size": args.tournament_size,
        "elitism_size": args.elitism_size,
        "max_stagnation": args.max_stagnation,
    }

    logger.info("=" * 60)
    logger.info("智能排课系统启动")
    logger.info("=" * 60)
    logger.info(f"版本ID: {args.version}")
    logger.info(f"遗传算法配置: {ga_config}")

    # 初始化系统
    system = SchedulingSystem()

    try:
        # 设置数据库连接
        system.setup_database_connection()

        # 运行排课
        success = system.run_scheduling(args.version, ga_config)

        if success:
            logger.info("排课任务完成成功！")
            sys.exit(0)
        else:
            logger.error("排课任务执行失败！")
            sys.exit(1)

    except KeyboardInterrupt:
        logger.info("用户中断程序")
        sys.exit(1)
    except Exception as e:
        logger.error(f"系统异常: {e}")
        import traceback

        logger.error(traceback.format_exc())
        sys.exit(1)
    finally:
        system.cleanup()


if __name__ == "__main__":
    main()
