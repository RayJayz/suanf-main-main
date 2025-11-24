#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
分析排课结果中的冲突问题
支持导出冲突Excel和优化冲突
"""
import os
import sys
import pymysql
from collections import defaultdict
from datetime import datetime
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill

# 设置标准输出编码为UTF-8
if sys.platform == "win32":
    import io

    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")


def export_conflicts_to_excel(
    class_conflicts, teacher_conflicts, classroom_conflicts, version_id
):
    """导出冲突到Excel"""
    wb = Workbook()

    # 样式定义
    header_fill = PatternFill(
        start_color="4472C4", end_color="4472C4", fill_type="solid"
    )
    header_font = Font(color="FFFFFF", bold=True, size=11)
    conflict_fill = PatternFill(
        start_color="FFC7CE", end_color="FFC7CE", fill_type="solid"
    )

    day_names = ["", "周一", "周二", "周三", "周四", "周五", "周六", "周日"]

    # 班级冲突表
    if wb.active:
        ws1 = wb.active
        ws1.title = "班级冲突"
    else:
        ws1 = wb.create_sheet("班级冲突")

    ws1.append(
        [
            "冲突序号",
            "班级",
            "星期",
            "节次",
            "课程1",
            "教师1",
            "教室1",
            "课程2",
            "教师2",
            "教室2",
        ]
    )
    for col in range(1, 11):
        ws1.cell(1, col).fill = header_fill
        ws1.cell(1, col).font = header_font
        ws1.cell(1, col).alignment = Alignment(horizontal="center", vertical="center")

    for idx, conflict in enumerate(class_conflicts, 1):
        items = conflict["items"]
        ws1.append(
            [
                idx,
                conflict["class_name"],
                day_names[conflict["weekday"]],
                conflict["slot"],
                items[0]["course"],
                items[0]["teacher"],
                items[0]["classroom"],
                items[1]["course"] if len(items) > 1 else "",
                items[1]["teacher"] if len(items) > 1 else "",
                items[1]["classroom"] if len(items) > 1 else "",
            ]
        )
        for col in range(1, 11):
            ws1.cell(idx + 1, col).fill = conflict_fill

    # 调整列宽
    ws1.column_dimensions["A"].width = 10
    ws1.column_dimensions["B"].width = 20
    ws1.column_dimensions["C"].width = 8
    ws1.column_dimensions["D"].width = 8
    for col in ["E", "F", "G", "H", "I", "J"]:
        ws1.column_dimensions[col].width = 20

    # 教师冲突表
    ws2 = wb.create_sheet("教师冲突")
    ws2.append(["冲突序号", "教师", "星期", "节次", "课程1", "教室1", "课程2", "教室2"])
    for col in range(1, 9):
        ws2.cell(1, col).fill = header_fill
        ws2.cell(1, col).font = header_font
        ws2.cell(1, col).alignment = Alignment(horizontal="center", vertical="center")

    for idx, conflict in enumerate(teacher_conflicts, 1):
        items = conflict["items"]
        ws2.append(
            [
                idx,
                conflict["teacher"],
                day_names[conflict["weekday"]],
                conflict["slot"],
                items[0]["course"],
                items[0]["classroom"],
                items[1]["course"] if len(items) > 1 else "",
                items[1]["classroom"] if len(items) > 1 else "",
            ]
        )
        for col in range(1, 9):
            ws2.cell(idx + 1, col).fill = conflict_fill

    ws2.column_dimensions["A"].width = 10
    ws2.column_dimensions["B"].width = 20
    ws2.column_dimensions["C"].width = 8
    ws2.column_dimensions["D"].width = 8
    for col in ["E", "F", "G", "H"]:
        ws2.column_dimensions[col].width = 20

    # 教室冲突表
    ws3 = wb.create_sheet("教室冲突")
    ws3.append(["冲突序号", "教室", "星期", "节次", "课程1", "教师1", "课程2", "教师2"])
    for col in range(1, 9):
        ws3.cell(1, col).fill = header_fill
        ws3.cell(1, col).font = header_font
        ws3.cell(1, col).alignment = Alignment(horizontal="center", vertical="center")

    for idx, conflict in enumerate(classroom_conflicts, 1):
        items = conflict["items"]
        ws3.append(
            [
                idx,
                conflict["classroom"],
                day_names[conflict["weekday"]],
                conflict["slot"],
                items[0]["course"],
                items[0]["teacher"],
                items[1]["course"] if len(items) > 1 else "",
                items[1]["teacher"] if len(items) > 1 else "",
            ]
        )
        for col in range(1, 9):
            ws3.cell(idx + 1, col).fill = conflict_fill

    ws3.column_dimensions["A"].width = 10
    ws3.column_dimensions["B"].width = 20
    ws3.column_dimensions["C"].width = 8
    ws3.column_dimensions["D"].width = 8
    for col in ["E", "F", "G", "H"]:
        ws3.column_dimensions[col].width = 20

    # 保存文件
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"排课冲突报告_版本{version_id}_{timestamp}.xlsx"
    wb.save(filename)
    print(f"\n✓ 冲突报告已导出到: {filename}")
    return filename


def analyze_schedule_conflicts(version_id):
    """分析指定版本的排课冲突"""

    # 连接数据库
    conn = pymysql.connect(
        host=os.getenv("DB_HOST") or "localhost",
        port=int(os.getenv("DB_PORT") or "3306"),
        user=os.getenv("DB_USER") or "root",
        password=os.getenv("DB_PASSWORD") or "20051113Da",
        database=os.getenv("DB_NAME") or "paike2",
        charset="utf8mb4",
    )

    try:
        cursor = conn.cursor(pymysql.cursors.DictCursor)

        # 获取排课结果
        query = """
        SELECT 
            sr.schedule_id,
            sr.task_id,
            sr.classroom_id,
            sr.week_day,
            sr.start_slot,
            tt.slots_count,
            tt.offering_id,
            c.course_name,
            cr.classroom_name,
            GROUP_CONCAT(DISTINCT t.teacher_name SEPARATOR ', ') AS teacher_name,
            GROUP_CONCAT(DISTINCT t.teacher_id SEPARATOR ', ') AS teacher_ids
        FROM schedules sr
        JOIN teaching_tasks tt ON sr.task_id = tt.task_id
        JOIN course_offerings co ON tt.offering_id = co.offering_id
        JOIN courses c ON co.course_id = c.course_id
        JOIN classrooms cr ON sr.classroom_id = cr.classroom_id
        LEFT JOIN offering_teachers ot ON co.offering_id = ot.offering_id
        LEFT JOIN teachers t ON ot.teacher_id = t.teacher_id
        WHERE sr.version_id = %s
        GROUP BY sr.schedule_id, sr.task_id, sr.classroom_id, sr.week_day, 
                 sr.start_slot, tt.slots_count, tt.offering_id, c.course_name, cr.classroom_name
        ORDER BY sr.week_day, sr.start_slot
        """

        cursor.execute(query, (version_id,))
        results = cursor.fetchall()

        # 获取任务-班级关系
        task_classes = defaultdict(list)
        for result in results:
            task_id = result["task_id"]
            class_query = """
            SELECT cl.class_id, cl.class_name
            FROM offering_classes oc
            JOIN classes cl ON oc.class_id = cl.class_id
            JOIN teaching_tasks tt ON oc.offering_id = tt.offering_id
            WHERE tt.task_id = %s
            """
            cursor.execute(class_query, (task_id,))
            classes = cursor.fetchall()
            task_classes[task_id] = classes

        print("=" * 80)
        print(f"排课版本 {version_id} 冲突分析报告")
        print("=" * 80)

        # 分析班级冲突
        print("\n【班级时间冲突分析】")
        class_schedule = defaultdict(list)
        class_conflicts_data = []  # 用于导出

        for result in results:
            task_id = result["task_id"]
            start_slot = result["start_slot"]
            end_slot = start_slot + result["slots_count"] - 1
            week_day = result["week_day"]

            for cls in task_classes[task_id]:
                class_id = cls["class_id"]
                for slot in range(start_slot, end_slot + 1):
                    time_key = (week_day, slot)
                    class_schedule[class_id].append(
                        {
                            "time": time_key,
                            "course": result["course_name"],
                            "teacher": result["teacher_name"],
                            "classroom": result["classroom_name"],
                            "class_name": cls["class_name"],
                        }
                    )

        # 检测冲突
        conflicts_found = 0
        for class_id, schedule in class_schedule.items():
            time_dict = defaultdict(list)
            for item in schedule:
                time_dict[item["time"]].append(item)

            for time, items in time_dict.items():
                if len(items) > 1:
                    conflicts_found += 1
                    week_day, slot = time
                    day_names = [
                        "",
                        "周一",
                        "周二",
                        "周三",
                        "周四",
                        "周五",
                        "周六",
                        "周日",
                    ]
                    print(f"\n冲突 #{conflicts_found}:")
                    print(f"  班级: {items[0]['class_name']}")
                    print(f"  时间: {day_names[week_day]} 第{slot}节")
                    for i, item in enumerate(items, 1):
                        print(
                            f"  课程{i}: {item['course']} - {item['teacher']} - {item['classroom']}"
                        )

                    # 记录冲突数据用于导出
                    class_conflicts_data.append(
                        {
                            "class_name": items[0]["class_name"],
                            "weekday": week_day,
                            "slot": slot,
                            "items": items,
                        }
                    )

        if conflicts_found == 0:
            print("✓ 未发现班级冲突")
        else:
            print(f"\n⚠ 共发现 {conflicts_found} 处班级冲突")

        # 分析教师冲突
        print("\n【教师时间冲突分析】")
        teacher_schedule = defaultdict(list)
        teacher_conflicts_data = []  # 用于导出

        for result in results:
            # 从 teacher_ids 字段获取教师ID列表
            teacher_ids_str = result.get("teacher_ids", "")
            if not teacher_ids_str:
                continue

            teacher_ids = teacher_ids_str.split(", ")
            start_slot = result["start_slot"]
            end_slot = start_slot + result["slots_count"] - 1
            week_day = result["week_day"]

            for teacher_id in teacher_ids:
                for slot in range(start_slot, end_slot + 1):
                    time_key = (week_day, slot)
                    teacher_schedule[teacher_id].append(
                        {
                            "time": time_key,
                            "course": result["course_name"],
                            "teacher": result["teacher_name"],
                            "classroom": result["classroom_name"],
                        }
                    )

        teacher_conflicts = 0
        for teacher_id, schedule in teacher_schedule.items():
            time_dict = defaultdict(list)
            for item in schedule:
                time_dict[item["time"]].append(item)

            for time, items in time_dict.items():
                if len(items) > 1:
                    teacher_conflicts += 1
                    week_day, slot = time
                    day_names = [
                        "",
                        "周一",
                        "周二",
                        "周三",
                        "周四",
                        "周五",
                        "周六",
                        "周日",
                    ]
                    print(f"\n冲突 #{teacher_conflicts}:")
                    print(f"  教师: {items[0]['teacher']}")
                    print(f"  时间: {day_names[week_day]} 第{slot}节")
                    for i, item in enumerate(items, 1):
                        print(f"  课程{i}: {item['course']} - {item['classroom']}")

                    # 记录冲突数据用于导出
                    teacher_conflicts_data.append(
                        {
                            "teacher": items[0]["teacher"],
                            "weekday": week_day,
                            "slot": slot,
                            "items": items,
                        }
                    )

        if teacher_conflicts == 0:
            print("✓ 未发现教师冲突")
        else:
            print(f"\n⚠ 共发现 {teacher_conflicts} 处教师冲突")

        # 分析教室冲突
        print("\n【教室时间冲突分析】")
        classroom_schedule = defaultdict(list)
        classroom_conflicts_data = []  # 用于导出

        for result in results:
            classroom_id = result["classroom_id"]
            start_slot = result["start_slot"]
            end_slot = start_slot + result["slots_count"] - 1
            week_day = result["week_day"]

            for slot in range(start_slot, end_slot + 1):
                time_key = (week_day, slot)
                classroom_schedule[classroom_id].append(
                    {
                        "time": time_key,
                        "course": result["course_name"],
                        "teacher": result["teacher_name"],
                        "classroom": result["classroom_name"],
                    }
                )

        classroom_conflicts = 0
        for classroom_id, schedule in classroom_schedule.items():
            time_dict = defaultdict(list)
            for item in schedule:
                time_dict[item["time"]].append(item)

            for time, items in time_dict.items():
                if len(items) > 1:
                    classroom_conflicts += 1
                    week_day, slot = time
                    day_names = [
                        "",
                        "周一",
                        "周二",
                        "周三",
                        "周四",
                        "周五",
                        "周六",
                        "周日",
                    ]
                    print(f"\n冲突 #{classroom_conflicts}:")
                    print(f"  教室: {items[0]['classroom']}")
                    print(f"  时间: {day_names[week_day]} 第{slot}节")
                    for i, item in enumerate(items, 1):
                        print(f"  课程{i}: {item['course']} - {item['teacher']}")

                    # 记录冲突数据用于导出
                    classroom_conflicts_data.append(
                        {
                            "classroom": items[0]["classroom"],
                            "weekday": week_day,
                            "slot": slot,
                            "items": items,
                        }
                    )

        if classroom_conflicts == 0:
            print("✓ 未发现教室冲突")
        else:
            print(f"\n⚠ 共发现 {classroom_conflicts} 处教室冲突")

        print("\n" + "=" * 80)
        print("分析完成")
        print("=" * 80)

        # 导出冲突Excel
        total_conflicts = conflicts_found + teacher_conflicts + classroom_conflicts
        if total_conflicts > 0:
            export_conflicts_to_excel(
                class_conflicts_data,
                teacher_conflicts_data,
                classroom_conflicts_data,
                version_id,
            )

            # 询问是否优化冲突
            print("\n" + "=" * 80)
            choice = input("是否尝试优化这些冲突? (y/n): ").strip().lower()
            if choice == "y":
                optimize_conflicts(
                    version_id,
                    results,
                    task_classes,
                    class_conflicts_data,
                    teacher_conflicts_data,
                    classroom_conflicts_data,
                    cursor,
                    conn,
                )
        else:
            # 即使没有硬约束冲突，也分析个性化要求满足情况
            print("\n" + "=" * 80)
            print("个性化要求满足情况分析")
            print("=" * 80)
            show_remaining_preference_violations(version_id, cursor)
            
            # 询问是否优化个性化要求
            print("\n" + "=" * 80)
            choice = input("是否尝试优化个性化要求? (y/n): ").strip().lower()
            if choice == "y":
                optimize_preferences(version_id, results, task_classes, cursor, conn)

    finally:
        cursor.close()
        conn.close()


def optimize_conflicts(
    version_id,
    results,
    task_classes,
    class_conflicts_data,
    teacher_conflicts_data,
    classroom_conflicts_data,
    cursor,
    conn,
):
    """优化冲突课程 - 分两阶段：1.解决硬约束冲突 2.满足个性化要求"""
    print("\n" + "=" * 80)
    print("开始优化冲突（两阶段策略）...")
    print("第一阶段：解决硬约束冲突（教师/班级/教室时间冲突）")
    print("第二阶段：在不违反硬约束的前提下满足个性化要求")
    print("=" * 80)

    # 收集所有有冲突的 schedule_id
    conflict_schedule_ids = set()

    # 从班级冲突中提取
    for conflict in class_conflicts_data:
        for item in conflict["items"]:
            # 找到对应的schedule记录 (修复: 检查冲突slot是否在课程的时间范围内)
            for result in results:
                start = result["start_slot"]
                end = start + result["slots_count"] - 1
                if (
                    result["course_name"] == item["course"]
                    and result["classroom_name"] == item["classroom"]
                    and result["week_day"] == conflict["weekday"]
                    and start <= conflict["slot"] <= end
                ):
                    conflict_schedule_ids.add(result["schedule_id"])

    # 从教师冲突中提取
    for conflict in teacher_conflicts_data:
        for item in conflict["items"]:
            for result in results:
                start = result["start_slot"]
                end = start + result["slots_count"] - 1
                if (
                    result["course_name"] == item["course"]
                    and result["classroom_name"] == item["classroom"]
                    and result["week_day"] == conflict["weekday"]
                    and start <= conflict["slot"] <= end
                ):
                    conflict_schedule_ids.add(result["schedule_id"])

    # 从教室冲突中提取
    for conflict in classroom_conflicts_data:
        for item in conflict["items"]:
            for result in results:
                start = result["start_slot"]
                end = start + result["slots_count"] - 1
                if (
                    result["course_name"] == item["course"]
                    and result["classroom_name"] == item["classroom"]
                    and result["week_day"] == conflict["weekday"]
                    and start <= conflict["slot"] <= end
                ):
                    conflict_schedule_ids.add(result["schedule_id"])

    print(f"\n第一阶段：识别到 {len(conflict_schedule_ids)} 个有硬约束冲突的课程安排")

    if len(conflict_schedule_ids) == 0:
        print("✓ 没有硬约束冲突")
        # 即使没有硬约束冲突，也可以尝试优化个性化要求
        optimize_preferences(version_id, results, task_classes, cursor, conn)
        return

    # 获取已占用的时间槽(不包括待调整的课程)
    occupied_times = defaultdict(
        lambda: defaultdict(set)
    )  # [entity_type][entity_id] = set of (weekday, slot)

    for result in results:
        if result["schedule_id"] in conflict_schedule_ids:
            continue  # 跳过冲突课程

        task_id = result["task_id"]
        start_slot = result["start_slot"]
        end_slot = start_slot + result["slots_count"] - 1
        weekday = result["week_day"]
        classroom_id = result["classroom_id"]

        # 记录教室占用
        for slot in range(start_slot, end_slot + 1):
            occupied_times["classroom"][classroom_id].add((weekday, slot))

        # 记录教师占用
        teacher_ids_str = result.get("teacher_ids", "")
        if teacher_ids_str:
            for teacher_id in teacher_ids_str.split(", "):
                for slot in range(start_slot, end_slot + 1):
                    occupied_times["teacher"][teacher_id].add((weekday, slot))

        # 记录班级占用
        for cls in task_classes[task_id]:
            class_id = cls["class_id"]
            for slot in range(start_slot, end_slot + 1):
                occupied_times["class"][class_id].add((weekday, slot))

    # ========== 第一阶段：解决硬约束冲突 ==========
    print("\n正在为有冲突的课程寻找无冲突时间槽...")
    adjustments = []
    day_names = ["", "周一", "周二", "周三", "周四", "周五", "周六", "周日"]

    for schedule_id in conflict_schedule_ids:
        # 找到对应的排课记录
        schedule_record = None
        for result in results:
            if result["schedule_id"] == schedule_id:
                schedule_record = result
                break

        if not schedule_record:
            continue

        task_id = schedule_record["task_id"]
        slots_count = schedule_record["slots_count"]
        classroom_id = schedule_record["classroom_id"]
        old_weekday = schedule_record["week_day"]
        old_start_slot = schedule_record["start_slot"]

        # 获取教师和班级
        teacher_ids = schedule_record.get("teacher_ids", "").split(", ")
        teacher_ids = [tid for tid in teacher_ids if tid]  # 过滤空字符串
        classes = [cls["class_id"] for cls in task_classes[task_id]]

        print(f"\n正在为 {schedule_record['course_name']} 寻找新时间...")
        print(
            f"  当前: {day_names[old_weekday]} 第{old_start_slot}-{old_start_slot+slots_count-1}节"
        )
        print(
            f"  教师: {len(teacher_ids)}个, 班级: {len(classes)}个, 教室: {classroom_id}"
        )

        # 尝试找到新的时间槽
        found_slot = False
        time_slots = []

        # 生成可能的时间槽 (周一到周五, 1-13节)
        for weekday in range(1, 6):  # 周一到周五
            for start_slot in range(1, 14 - slots_count + 1):
                # 跳过周四下午
                if weekday == 4 and start_slot >= 6:
                    continue

                # 检查是否有冲突
                has_conflict = False

                # 检查教室冲突
                for slot in range(start_slot, start_slot + slots_count):
                    if (weekday, slot) in occupied_times["classroom"][classroom_id]:
                        has_conflict = True
                        break

                if has_conflict:
                    continue

                # 检查教师冲突
                for teacher_id in teacher_ids:
                    for slot in range(start_slot, start_slot + slots_count):
                        if (weekday, slot) in occupied_times["teacher"][teacher_id]:
                            has_conflict = True
                            break
                    if has_conflict:
                        break

                if has_conflict:
                    continue

                # 检查班级冲突
                for class_id in classes:
                    for slot in range(start_slot, start_slot + slots_count):
                        if (weekday, slot) in occupied_times["class"][class_id]:
                            has_conflict = True
                            break
                    if has_conflict:
                        break

                if not has_conflict:
                    time_slots.append((weekday, start_slot))

        print(f"  找到 {len(time_slots)} 个候选时间槽")

        if time_slots:
            # 优先选择不同于原时间的槽位
            new_weekday, new_start_slot = None, None
            for weekday, start_slot in time_slots:
                if weekday != old_weekday or start_slot != old_start_slot:
                    new_weekday, new_start_slot = weekday, start_slot
                    break

            # 如果所有时间槽都是原时间，说明该课程可以留在原位
            # 这种情况下，跳过该课程，让其他冲突课程调整
            if new_weekday is None:
                print(f"  → 保留在原位，等待其他冲突课程调整")
                continue  # 更新占用记录
            for slot in range(new_start_slot, new_start_slot + slots_count):
                occupied_times["classroom"][classroom_id].add((new_weekday, slot))
                for teacher_id in teacher_ids:
                    occupied_times["teacher"][teacher_id].add((new_weekday, slot))
                for class_id in classes:
                    occupied_times["class"][class_id].add((new_weekday, slot))

            adjustments.append(
                {
                    "schedule_id": schedule_id,
                    "course_name": schedule_record["course_name"],
                    "old_time": (old_weekday, old_start_slot),
                    "new_time": (new_weekday, new_start_slot),
                    "new_end_slot": new_start_slot + slots_count - 1,
                }
            )
        else:
            print(f"⚠ 无法为课程 {schedule_record['course_name']} 找到合适的时间槽")
            print(f"   原时间: {day_names[old_weekday]} 第{old_start_slot}节")
            print(
                f"   课程信息: {slots_count}节课, 教室{classroom_id}, {len(teacher_ids)}个教师, {len(classes)}个班级"
            )

            # 诊断：检查是否有可用时间（不考虑教室和教师限制）
            available_for_class = []
            day_names_local = ["", "周一", "周二", "周三", "周四", "周五"]
            for weekday in range(1, 6):
                for start_slot in range(1, 14 - slots_count + 1):
                    if weekday == 4 and start_slot >= 6:
                        continue

                    # 只检查班级冲突
                    has_class_conflict = False
                    for class_id in classes:
                        for slot in range(start_slot, start_slot + slots_count):
                            if (weekday, slot) in occupied_times["class"][class_id]:
                                has_class_conflict = True
                                break
                        if has_class_conflict:
                            break

                    if not has_class_conflict and (
                        weekday != old_weekday or start_slot != old_start_slot
                    ):
                        available_for_class.append(
                            f"{day_names_local[weekday]}{start_slot}-{start_slot+slots_count-1}"
                        )

            if available_for_class:
                print(
                    f"   班级空闲时间: {', '.join(available_for_class[:5])}"
                    + (
                        f" 等{len(available_for_class)}个"
                        if len(available_for_class) > 5
                        else ""
                    )
                )
                print(f"   → 可能是教师或教室时间冲突导致无法调整")

    if adjustments:
        print(f"\n找到 {len(adjustments)} 个调整方案:")
        day_names = ["", "周一", "周二", "周三", "周四", "周五", "周六", "周日"]
        for adj in adjustments:
            old_day, old_slot = adj["old_time"]
            new_day, new_slot = adj["new_time"]
            print(
                f"  {adj['course_name']}: {day_names[old_day]} 第{old_slot}节 -> {day_names[new_day]} 第{new_slot}节"
            )

        confirm = input("\n确认应用这些调整? (y/n): ").strip().lower()
        if confirm == "y":
            # 应用调整到数据库
            for adj in adjustments:
                update_query = """
                UPDATE schedules 
                SET week_day = %s, start_slot = %s, end_slot = %s
                WHERE schedule_id = %s
                """
                cursor.execute(
                    update_query,
                    (
                        adj["new_time"][0],
                        adj["new_time"][1],
                        adj["new_end_slot"],
                        adj["schedule_id"],
                    ),
                )

            conn.commit()
            print(f"\n✓ 第一阶段完成：已成功调整 {len(adjustments)} 个课程安排，解决硬约束冲突")
            
            # 第二阶段：优化个性化要求
            print("\n" + "=" * 80)
            print("第二阶段：优化个性化要求（教师偏好时间）")
            print("=" * 80)
            optimize_preferences(version_id, results, task_classes, cursor, conn)
        else:
            print("\n已取消调整")
    else:
        print("\n⚠ 未找到可行的调整方案解决所有硬约束冲突")
        print("建议：")
        print("  1. 检查教室资源是否充足")
        print("  2. 检查教师时间是否过于紧张")
        print("  3. 考虑调整课程节数或增加教室/教师资源")


def optimize_preferences(version_id, results, task_classes, cursor, conn):
    """第二阶段：在不违反硬约束的前提下，优化个性化要求（教师偏好时间）"""
    from collections import defaultdict
    
    # 获取教师偏好设置
    pref_query = """
    SELECT 
        tp.preference_id,
        tp.offering_id,
        tp.teacher_id,
        tp.preference_type,
        tp.weekday,
        tp.start_slot,
        tp.end_slot,
        tp.penalty_score,
        t.teacher_name
    FROM teacher_preferences tp
    JOIN teachers t ON tp.teacher_id = t.teacher_id
    WHERE tp.offering_id IN (
        SELECT DISTINCT tt.offering_id 
        FROM teaching_tasks tt
        JOIN schedules s ON tt.task_id = s.task_id
        WHERE s.version_id = %s
    )
    ORDER BY tp.penalty_score DESC, tp.preference_type
    """
    
    cursor.execute(pref_query, (version_id,))
    preferences = cursor.fetchall()
    
    if not preferences:
        print("\n✓ 没有设置教师个性化要求")
        return
    
    print(f"\n找到 {len(preferences)} 条教师个性化要求")
    
    # 分类统计
    preferred_prefs = [p for p in preferences if p['preference_type'] == 'PREFERRED']
    avoided_prefs = [p for p in preferences if p['preference_type'] == 'AVOIDED']
    
    print(f"  - 偏好时间（PREFERRED）: {len(preferred_prefs)} 条")
    print(f"  - 避免时间（AVOIDED）: {len(avoided_prefs)} 条")
    
    # 构建当前占用情况（用于检查硬约束）
    occupied_times = defaultdict(lambda: defaultdict(set))
    schedule_map = {}  # schedule_id -> result
    
    for result in results:
        schedule_id = result['schedule_id']
        task_id = result['task_id']
        start_slot = result['start_slot']
        end_slot = start_slot + result['slots_count'] - 1
        weekday = result['week_day']
        classroom_id = result['classroom_id']
        
        schedule_map[schedule_id] = result
        
        # 记录占用
        for slot in range(start_slot, end_slot + 1):
            occupied_times['classroom'][classroom_id].add((weekday, slot))
            
            teacher_ids_str = result.get('teacher_ids', '')
            if teacher_ids_str:
                for teacher_id in teacher_ids_str.split(', '):
                    occupied_times['teacher'][teacher_id].add((weekday, slot))
            
            for cls in task_classes[task_id]:
                occupied_times['class'][cls['class_id']].add((weekday, slot))
    
    # 分析当前个性化要求满足情况
    print("\n分析当前个性化要求满足情况...")
    
    violated_preferred = []  # 未满足的偏好时间
    violated_avoided = []    # 违反的避免时间
    
    day_names = ["", "周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    
    for pref in preferences:
        teacher_id = pref['teacher_id']
        teacher_name = pref['teacher_name']
        pref_type = pref['preference_type']
        weekday = pref['weekday']
        start_slot = pref['start_slot']
        end_slot = pref['end_slot']
        
        if not weekday or not start_slot or not end_slot:
            continue
        
        # 查找该教师在该偏好时间段的课程
        teacher_schedule = occupied_times['teacher'][teacher_id]
        
        has_class_in_range = False
        for wd, slot in teacher_schedule:
            if wd == weekday and start_slot <= slot <= end_slot:
                has_class_in_range = True
                break
        
        if pref_type == 'PREFERRED' and not has_class_in_range:
            violated_preferred.append(pref)
        elif pref_type == 'AVOIDED' and has_class_in_range:
            violated_avoided.append(pref)
    
    print(f"\n个性化要求满足情况：")
    print(f"  ✓ 偏好时间已满足: {len(preferred_prefs) - len(violated_preferred)}/{len(preferred_prefs)}")
    print(f"  ✓ 避免时间已遵守: {len(avoided_prefs) - len(violated_avoided)}/{len(avoided_prefs)}")
    
    if violated_preferred:
        print(f"\n  ⚠ 未满足的偏好时间: {len(violated_preferred)} 条")
        for i, pref in enumerate(violated_preferred[:5], 1):
            print(f"    [{i}] {pref['teacher_name']}: {day_names[pref['weekday']]} {pref['start_slot']}-{pref['end_slot']}节")
        if len(violated_preferred) > 5:
            print(f"    ... 还有 {len(violated_preferred) - 5} 条")
    
    if violated_avoided:
        print(f"\n  ⚠ 违反的避免时间: {len(violated_avoided)} 条")
        for i, pref in enumerate(violated_avoided[:5], 1):
            print(f"    [{i}] {pref['teacher_name']}: {day_names[pref['weekday']]} {pref['start_slot']}-{pref['end_slot']}节")
        if len(violated_avoided) > 5:
            print(f"    ... 还有 {len(violated_avoided) - 5} 条")
    
    # 尝试优化个性化要求
    total_violations = len(violated_preferred) + len(violated_avoided)
    if total_violations == 0:
        print("\n✓ 所有个性化要求都已满足，无需优化")
        return
    
    print(f"\n尝试优化 {total_violations} 条未满足的个性化要求...")
    print("注意：只会调整不违反硬约束（教师/班级/教室冲突）的课程")
    
    preference_adjustments = []
    
    # 优先处理违反避免时间的情况（penalty更高）
    for pref in sorted(violated_avoided, key=lambda x: x['penalty_score'], reverse=True):
        # 找到该教师在该时间段的课程
        teacher_id = pref['teacher_id']
        weekday = pref['weekday']
        start_slot = pref['start_slot']
        end_slot = pref['end_slot']
        
        # 查找需要调整的schedule
        for schedule_id, result in schedule_map.items():
            teacher_ids_str = result.get('teacher_ids', '')
            if teacher_id not in teacher_ids_str.split(', '):
                continue
            
            if result['week_day'] != weekday:
                continue
            
            # 检查时间是否重叠
            result_start = result['start_slot']
            result_end = result_start + result['slots_count'] - 1
            
            if not (result_end < start_slot or result_start > end_slot):
                # 找到冲突课程，尝试调整
                new_time = find_alternative_time_for_preference(
                    result, task_classes, occupied_times, schedule_id, 
                    avoid_time=(weekday, start_slot, end_slot)
                )
                
                if new_time:
                    preference_adjustments.append({
                        'schedule_id': schedule_id,
                        'course_name': result['course_name'],
                        'teacher_name': pref['teacher_name'],
                        'old_time': (result['week_day'], result['start_slot']),
                        'new_time': new_time,
                        'reason': f"避免时间 {day_names[weekday]} {start_slot}-{end_slot}节",
                        'result': result
                    })
    
    # 尝试满足偏好时间
    for pref in sorted(violated_preferred, key=lambda x: x['penalty_score'], reverse=True)[:10]:  # 限制处理数量
        teacher_id = pref['teacher_id']
        weekday = pref['weekday']
        start_slot = pref['start_slot']
        end_slot = pref['end_slot']
        
        # 找到该教师的课程，尝试移到偏好时间
        for schedule_id, result in schedule_map.items():
            teacher_ids_str = result.get('teacher_ids', '')
            if teacher_id not in teacher_ids_str.split(', '):
                continue
            
            # 如果已经在调整列表中，跳过
            if any(adj['schedule_id'] == schedule_id for adj in preference_adjustments):
                continue
            
            # 尝试移到偏好时间段
            new_time = find_alternative_time_for_preference(
                result, task_classes, occupied_times, schedule_id,
                prefer_time=(weekday, start_slot, end_slot)
            )
            
            if new_time and new_time[0] == weekday and start_slot <= new_time[1] <= end_slot:
                preference_adjustments.append({
                    'schedule_id': schedule_id,
                    'course_name': result['course_name'],
                    'teacher_name': pref['teacher_name'],
                    'old_time': (result['week_day'], result['start_slot']),
                    'new_time': new_time,
                    'reason': f"满足偏好时间 {day_names[weekday]} {start_slot}-{end_slot}节",
                    'result': result
                })
                break  # 每个偏好只调整一门课
    
    if preference_adjustments:
        print(f"\n找到 {len(preference_adjustments)} 个可优化的课程安排：")
        for i, adj in enumerate(preference_adjustments, 1):
            old_day, old_slot = adj['old_time']
            new_day, new_slot = adj['new_time']
            print(f"  [{i}] {adj['course_name']} ({adj['teacher_name']})")
            print(f"      {day_names[old_day]} 第{old_slot}节 -> {day_names[new_day]} 第{new_slot}节")
            print(f"      原因: {adj['reason']}")
        
        confirm = input("\n确认应用这些优化? (y/n): ").strip().lower()
        if confirm == 'y':
            for adj in preference_adjustments:
                result = adj['result']
                new_day, new_slot = adj['new_time']
                new_end_slot = new_slot + result['slots_count'] - 1
                
                update_query = """
                UPDATE schedules 
                SET week_day = %s, start_slot = %s, end_slot = %s
                WHERE schedule_id = %s
                """
                cursor.execute(update_query, (new_day, new_slot, new_end_slot, adj['schedule_id']))
            
            conn.commit()
            print(f"\n✓ 第二阶段完成：已优化 {len(preference_adjustments)} 个课程以满足个性化要求")
            
            # 重新分析优化后的个性化要求满足情况
            print("\n" + "=" * 80)
            print("重新分析优化后的个性化要求满足情况...")
            print("=" * 80)
            show_remaining_preference_violations(version_id, cursor)
            
            print("\n建议重新运行冲突分析验证结果")
        else:
            print("\n已取消优化")
    else:
        print("\n未找到可以优化的方案（所有调整都会违反硬约束）")
        
        # 即使无法优化，也显示当前未满足的个性化要求
        if total_violations > 0:
            print("\n" + "=" * 80)
            print("当前仍未满足的个性化要求详情：")
            print("=" * 80)
            show_remaining_preference_violations(version_id, cursor)


def find_alternative_time_for_preference(result, task_classes, occupied_times, 
                                         current_schedule_id, avoid_time=None, prefer_time=None):
    """为课程寻找替代时间，考虑个性化要求
    
    Args:
        result: 当前排课记录
        task_classes: 任务-班级映射
        occupied_times: 已占用时间
        current_schedule_id: 当前schedule_id（需要从占用时间中排除）
        avoid_time: 要避免的时间段 (weekday, start_slot, end_slot)
        prefer_time: 偏好的时间段 (weekday, start_slot, end_slot)
    """
    task_id = result['task_id']
    slots_count = result['slots_count']
    classroom_id = result['classroom_id']
    teacher_ids = result.get('teacher_ids', '').split(', ')
    teacher_ids = [tid for tid in teacher_ids if tid]
    classes = [cls['class_id'] for cls in task_classes[task_id]]
    
    # 临时移除当前课程的占用
    old_weekday = result['week_day']
    old_start = result['start_slot']
    old_end = old_start + slots_count - 1
    
    temp_removed = []
    for slot in range(old_start, old_end + 1):
        occupied_times['classroom'][classroom_id].discard((old_weekday, slot))
        for tid in teacher_ids:
            occupied_times['teacher'][tid].discard((old_weekday, slot))
        for cid in classes:
            occupied_times['class'][cid].discard((old_weekday, slot))
    
    candidate_times = []
    
    # 如果有偏好时间，优先考虑
    if prefer_time:
        pref_weekday, pref_start, pref_end = prefer_time
        for start_slot in range(pref_start, min(pref_end, 14 - slots_count) + 1):
            if pref_weekday == 4 and start_slot >= 6:  # 周四下午
                continue
            
            if check_time_available(pref_weekday, start_slot, slots_count, 
                                   classroom_id, teacher_ids, classes, occupied_times):
                candidate_times.append((pref_weekday, start_slot, 0))  # 优先级0最高
    
    # 搜索其他可用时间
    for weekday in range(1, 6):  # 周一到周五
        for start_slot in range(1, 14 - slots_count + 1):
            if weekday == 4 and start_slot >= 6:  # 周四下午
                continue
            
            # 跳过避免时间
            if avoid_time:
                avoid_weekday, avoid_start, avoid_end = avoid_time
                if weekday == avoid_weekday and not (start_slot + slots_count - 1 < avoid_start or start_slot > avoid_end):
                    continue
            
            # 如果已经在偏好时间列表中，跳过
            if any(t[0] == weekday and t[1] == start_slot for t in candidate_times):
                continue
            
            if check_time_available(weekday, start_slot, slots_count,
                                   classroom_id, teacher_ids, classes, occupied_times):
                priority = 1 if (weekday, start_slot) != (old_weekday, old_start) else 2
                candidate_times.append((weekday, start_slot, priority))
    
    # 恢复占用
    for slot in range(old_start, old_end + 1):
        occupied_times['classroom'][classroom_id].add((old_weekday, slot))
        for tid in teacher_ids:
            occupied_times['teacher'][tid].add((old_weekday, slot))
        for cid in classes:
            occupied_times['class'][cid].add((old_weekday, slot))
    
    if candidate_times:
        # 按优先级排序
        candidate_times.sort(key=lambda x: x[2])
        return (candidate_times[0][0], candidate_times[0][1])
    
    return None


def check_time_available(weekday, start_slot, slots_count, classroom_id, 
                        teacher_ids, class_ids, occupied_times):
    """检查指定时间段是否可用（无硬约束冲突）"""
    for slot in range(start_slot, start_slot + slots_count):
        # 检查教室
        if (weekday, slot) in occupied_times['classroom'][classroom_id]:
            return False
        
        # 检查教师
        for tid in teacher_ids:
            if (weekday, slot) in occupied_times['teacher'][tid]:
                return False
        
        # 检查班级
        for cid in class_ids:
            if (weekday, slot) in occupied_times['class'][cid]:
                return False
    
    return True


def show_remaining_preference_violations(version_id, cursor):
    """显示当前仍未满足的个性化要求详情"""
    from collections import defaultdict
    
    # 获取当前排课结果（可能已被更新）
    query = """
    SELECT 
        sr.schedule_id,
        sr.task_id,
        sr.classroom_id,
        sr.week_day,
        sr.start_slot,
        tt.slots_count,
        c.course_name,
        GROUP_CONCAT(DISTINCT t.teacher_id SEPARATOR ', ') AS teacher_ids,
        GROUP_CONCAT(DISTINCT t.teacher_name SEPARATOR ', ') AS teacher_names
    FROM schedules sr
    JOIN teaching_tasks tt ON sr.task_id = tt.task_id
    JOIN course_offerings co ON tt.offering_id = co.offering_id
    JOIN courses c ON co.course_id = c.course_id
    LEFT JOIN offering_teachers ot ON co.offering_id = ot.offering_id
    LEFT JOIN teachers t ON ot.teacher_id = t.teacher_id
    WHERE sr.version_id = %s
    GROUP BY sr.schedule_id, sr.task_id, sr.classroom_id, sr.week_day, 
             sr.start_slot, tt.slots_count, c.course_name
    """
    
    cursor.execute(query, (version_id,))
    current_results = cursor.fetchall()
    
    # 构建教师实际排课时间
    teacher_schedules = defaultdict(list)
    for result in current_results:
        teacher_ids_str = result.get('teacher_ids', '')
        if not teacher_ids_str:
            continue
        
        teacher_ids = teacher_ids_str.split(', ')
        start_slot = result['start_slot']
        end_slot = start_slot + result['slots_count'] - 1
        weekday = result['week_day']
        
        for teacher_id in teacher_ids:
            for slot in range(start_slot, end_slot + 1):
                teacher_schedules[teacher_id].append({
                    'weekday': weekday,
                    'slot': slot,
                    'course_name': result['course_name']
                })
    
    # 获取教师偏好设置
    pref_query = """
    SELECT 
        tp.preference_id,
        tp.offering_id,
        tp.teacher_id,
        tp.preference_type,
        tp.weekday,
        tp.start_slot,
        tp.end_slot,
        tp.penalty_score,
        t.teacher_name
    FROM teacher_preferences tp
    JOIN teachers t ON tp.teacher_id = t.teacher_id
    WHERE tp.offering_id IN (
        SELECT DISTINCT tt.offering_id 
        FROM teaching_tasks tt
        JOIN schedules s ON tt.task_id = s.task_id
        WHERE s.version_id = %s
    )
    ORDER BY tp.penalty_score DESC, tp.preference_type
    """
    
    cursor.execute(pref_query, (version_id,))
    preferences = cursor.fetchall()
    
    if not preferences:
        print("\n✓ 没有设置教师个性化要求")
        return
    
    day_names = ["", "周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    
    # 分析未满足的个性化要求
    violated_preferred = []  # 未满足的偏好时间
    violated_avoided = []    # 违反的避免时间
    
    for pref in preferences:
        teacher_id = pref['teacher_id']
        teacher_name = pref['teacher_name']
        pref_type = pref['preference_type']
        weekday = pref['weekday']
        start_slot = pref['start_slot']
        end_slot = pref['end_slot']
        
        if not weekday or not start_slot or not end_slot:
            continue
        
        # 检查该教师在该时间段是否有课
        schedule = teacher_schedules.get(teacher_id, [])
        courses_in_range = []
        
        for sch in schedule:
            if sch['weekday'] == weekday and start_slot <= sch['slot'] <= end_slot:
                if sch['course_name'] not in [c['name'] for c in courses_in_range]:
                    courses_in_range.append({
                        'name': sch['course_name'],
                        'slot': sch['slot']
                    })
        
        has_class = len(courses_in_range) > 0
        
        if pref_type == 'PREFERRED' and not has_class:
            violated_preferred.append({
                'teacher_name': teacher_name,
                'weekday': weekday,
                'start_slot': start_slot,
                'end_slot': end_slot,
                'penalty_score': pref['penalty_score']
            })
        elif pref_type == 'AVOIDED' and has_class:
            violated_avoided.append({
                'teacher_name': teacher_name,
                'weekday': weekday,
                'start_slot': start_slot,
                'end_slot': end_slot,
                'penalty_score': pref['penalty_score'],
                'courses': courses_in_range
            })
    
    # 统计
    total_preferred = sum(1 for p in preferences if p['preference_type'] == 'PREFERRED')
    total_avoided = sum(1 for p in preferences if p['preference_type'] == 'AVOIDED')
    
    print(f"\n个性化要求满足情况汇总：")
    print(f"  偏好时间（PREFERRED）：")
    print(f"    总计: {total_preferred} 条")
    print(f"    已满足: {total_preferred - len(violated_preferred)} 条")
    print(f"    未满足: {len(violated_preferred)} 条")
    if total_preferred > 0:
        satisfaction_rate = (total_preferred - len(violated_preferred)) / total_preferred * 100
        print(f"    满足率: {satisfaction_rate:.1f}%")
    
    print(f"\n  避免时间（AVOIDED）：")
    print(f"    总计: {total_avoided} 条")
    print(f"    已遵守: {total_avoided - len(violated_avoided)} 条")
    print(f"    被违反: {len(violated_avoided)} 条")
    if total_avoided > 0:
        compliance_rate = (total_avoided - len(violated_avoided)) / total_avoided * 100
        print(f"    遵守率: {compliance_rate:.1f}%")
    
    # 显示详细的未满足情况
    if violated_preferred:
        print(f"\n仍未满足的偏好时间详情（共 {len(violated_preferred)} 条）：")
        # 按惩罚分数排序
        violated_preferred.sort(key=lambda x: x['penalty_score'], reverse=True)
        for i, item in enumerate(violated_preferred[:15], 1):  # 显示前15条
            print(f"  [{i}] 教师: {item['teacher_name']}")
            print(f"      偏好时间: {day_names[item['weekday']]} 第{item['start_slot']}-{item['end_slot']}节")
            print(f"      惩罚分数: {item['penalty_score']}")
        if len(violated_preferred) > 15:
            print(f"  ... 还有 {len(violated_preferred) - 15} 条未显示")
    else:
        print("\n✓ 所有偏好时间都已满足")
    
    if violated_avoided:
        print(f"\n仍被违反的避免时间详情（共 {len(violated_avoided)} 条）：")
        # 按惩罚分数排序
        violated_avoided.sort(key=lambda x: x['penalty_score'], reverse=True)
        for i, item in enumerate(violated_avoided[:15], 1):  # 显示前15条
            print(f"  [{i}] 教师: {item['teacher_name']}")
            print(f"      避免时间: {day_names[item['weekday']]} 第{item['start_slot']}-{item['end_slot']}节")
            print(f"      惩罚分数: {item['penalty_score']}")
            print(f"      冲突课程: {', '.join(set(c['name'] for c in item['courses']))}")
        if len(violated_avoided) > 15:
            print(f"  ... 还有 {len(violated_avoided) - 15} 条未显示")
    else:
        print("\n✓ 所有避免时间都已遵守")
    
    # 总体评估
    total_violations = len(violated_preferred) + len(violated_avoided)
    total_prefs = total_preferred + total_avoided
    
    if total_violations == 0:
        print("\n" + "=" * 80)
        print("🎉 所有个性化要求都已完美满足！")
        print("=" * 80)
    else:
        overall_satisfaction = (total_prefs - total_violations) / total_prefs * 100 if total_prefs > 0 else 100
        print(f"\n总体个性化要求满足率: {overall_satisfaction:.1f}% ({total_prefs - total_violations}/{total_prefs})")
        
        if total_violations > 0:
            print("\n建议：")
            print("  • 如果硬约束冲突已全部解决，但个性化要求仍未满足，")
            print("    可能是资源限制导致，建议：")
            print("    1. 放宽部分个性化要求的时间范围")
            print("    2. 降低部分个性化要求的优先级（penalty_score）")
            print("    3. 增加可用教室或调整课程时间安排")


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("用法: python analyze_conflicts.py <version_id>")
        print("示例: python analyze_conflicts.py 1")
        sys.exit(1)

    version_id = int(sys.argv[1])
    analyze_schedule_conflicts(version_id)
