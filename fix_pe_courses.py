#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
体育课教室问题诊断与修复方案
问题：体育课应该在室外（体育场/体育馆）上课，但当前被分配到室内教室
"""
import os
from db_connector import DatabaseConnector

def diagnose_pe_courses():
    """诊断体育课教室分配问题"""
    
    db_config = {
        "host": os.getenv("DB_HOST", "localhost"),
        "user": os.getenv("DB_USER", "root"),
        "password": os.getenv("DB_PASSWORD", "20051113Da"),
        "database": os.getenv("DB_NAME", "paike2"),
        "charset": "utf8mb4",
    }
    
    db = DatabaseConnector(**db_config)
    db.connect()
    
    try:
        print("=" * 80)
        print("体育课教室问题诊断报告")
        print("=" * 80)
        
        # 1. 检查体育课程
        print("\n【步骤1】检查体育课程列表")
        print("-" * 80)
        
        query_courses = """
        SELECT course_id, course_name, total_hours 
        FROM courses 
        WHERE course_id LIKE 'PHYE%'
        ORDER BY course_id
        """
        
        pe_courses = db.execute_query(query_courses)
        print(f"找到 {len(pe_courses)} 门体育课程:")
        for course in pe_courses:
            print(f"  - {course['course_id']}: {course['course_name']} ({course['total_hours']}学时)")
        
        # 2. 检查室外场地和体育馆
        print("\n【步骤2】检查现有的室外场地和体育馆")
        print("-" * 80)
        
        query_outdoor = """
        SELECT c.classroom_id, c.classroom_name, c.building_name, c.capacity,
               GROUP_CONCAT(cf.feature_name SEPARATOR ', ') as features
        FROM classrooms c
        LEFT JOIN classroom_has_features chf ON c.classroom_id = chf.classroom_id
        LEFT JOIN classroom_features cf ON chf.feature_id = cf.feature_id
        WHERE c.classroom_id LIKE '%体育%' 
           OR c.classroom_name LIKE '%体育%' 
           OR c.building_name LIKE '%体育%'
           OR chf.feature_id = 'SW'
        GROUP BY c.classroom_id, c.classroom_name, c.building_name, c.capacity
        """
        
        outdoor_classrooms = db.execute_query(query_outdoor)
        
        if outdoor_classrooms:
            print(f"找到 {len(outdoor_classrooms)} 个体育场地:")
            for room in outdoor_classrooms:
                print(f"  - {room['classroom_id']}: {room['classroom_name']} "
                      f"(容量:{room['capacity']}, 特征:{room['features'] or '无'})")
        else:
            print("⚠ 数据库中没有室外体育场地!")
        
        # 3. 检查体育课当前的教室分配
        print("\n【步骤3】检查体育课当前的教室分配情况")
        print("-" * 80)
        
        query_pe_schedule = """
        SELECT 
            c.course_id,
            c.course_name,
            cr.classroom_id,
            cr.classroom_name,
            cr.building_name,
            cr.capacity,
            GROUP_CONCAT(DISTINCT cf.feature_name SEPARATOR ', ') as features,
            COUNT(DISTINCT s.schedule_id) as schedule_count
        FROM courses c
        JOIN course_offerings co ON c.course_id = co.course_id
        JOIN teaching_tasks tt ON co.offering_id = tt.offering_id
        JOIN schedules s ON tt.task_id = s.task_id
        JOIN classrooms cr ON s.classroom_id = cr.classroom_id
        LEFT JOIN classroom_has_features chf ON cr.classroom_id = chf.classroom_id
        LEFT JOIN classroom_features cf ON chf.feature_id = cf.feature_id
        WHERE c.course_id LIKE 'PHYE%'
        GROUP BY c.course_id, c.course_name, cr.classroom_id, cr.classroom_name, 
                 cr.building_name, cr.capacity
        ORDER BY c.course_id, cr.classroom_id
        """
        
        pe_schedules = db.execute_query(query_pe_schedule)
        
        indoor_count = 0
        outdoor_count = 0
        
        if pe_schedules:
            print(f"体育课已排课情况 (共 {len(pe_schedules)} 条分配记录):")
            for sched in pe_schedules:
                is_outdoor = sched['features'] and 'SW' in sched['features']
                status = "✓ 室外" if is_outdoor else "✗ 室内"
                
                if is_outdoor:
                    outdoor_count += sched['schedule_count']
                else:
                    indoor_count += sched['schedule_count']
                
                print(f"  {status} {sched['course_name']}")
                print(f"      教室: {sched['classroom_name']} ({sched['building_name']})")
                print(f"      容量: {sched['capacity']}, 特征: {sched['features'] or '无'}")
                print(f"      排课次数: {sched['schedule_count']}")
        else:
            print("体育课尚未排课")
        
        # 4. 统计问题
        print("\n" + "=" * 80)
        print("问题统计")
        print("=" * 80)
        print(f"✓ 在室外场地的体育课: {outdoor_count} 次")
        print(f"✗ 在室内教室的体育课: {indoor_count} 次")
        
        if indoor_count > 0:
            print(f"\n⚠ 发现问题：有 {indoor_count} 次体育课被分配到室内教室！")
        
        # 5. 提供解决方案
        print("\n" + "=" * 80)
        print("解决方案")
        print("=" * 80)
        
        print("\n方案A: 在数据库中添加体育场地（推荐）")
        print("-" * 80)
        print("需要执行以下SQL语句：")
        print()
        print("-- 1. 添加室外特征（如果还没有）")
        print("INSERT INTO classroom_features (feature_id, feature_name, description)")
        print("VALUES ('SW', '室外', '室外场地') ON DUPLICATE KEY UPDATE feature_name='室外';")
        print()
        print("-- 2. 添加体育场地")
        print("INSERT INTO classrooms (classroom_id, classroom_name, building_name, campus_id, type, capacity, is_available)")
        print("VALUES ")
        print("('SPORT_N', '北区体育场', '北区体育场', 'DB', '室外', 500, 1),")
        print("('SPORT_S', '南区体育场', '南区体育场', 'DB', '室外', 500, 1),")
        print("('GYM_1', '体育馆1', '体育馆', 'DB', '室内', 200, 1),")
        print("('GYM_2', '体育馆2', '体育馆', 'DB', '室内', 200, 1);")
        print()
        print("-- 3. 为体育场地添加室外特征")
        print("INSERT INTO classroom_has_features (classroom_id, feature_id)")
        print("VALUES ")
        print("('SPORT_N', 'SW'),")
        print("('SPORT_S', 'SW'),")
        print("('GYM_1', 'SW'),")
        print("('GYM_2', 'SW');")
        print()
        print("-- 4. 设置体育课程需要室外场地特征")
        print("INSERT INTO course_required_features (course_id, feature_id)")
        print("VALUES ")
        print("('PHYE000111', 'SW'),")
        print("('PHYE000311', 'SW'),")
        print("('PHYE000511', 'SW')")
        print("ON DUPLICATE KEY UPDATE feature_id=feature_id;")
        
        print("\n方案B: 在代码中强制体育课使用特定教室")
        print("-" * 80)
        print("在 genetic_algorithm.py 中添加特殊处理逻辑：")
        print("- 检测体育课程（course_id 以 'PHYE' 开头）")
        print("- 强制为这些课程分配室外场地")
        print("- 如果没有室外场地，给予高额惩罚")
        
        print("\n方案C: 手动调整已排课程")
        print("-" * 80)
        if indoor_count > 0:
            print("如果体育场地已添加，运行以下命令重新为体育课分配教室：")
            print("python analyze_conflicts.py <version_id>")
            print("然后选择优化冲突，系统会自动将体育课调整到合适的场地")
        
        return {
            'pe_courses': len(pe_courses),
            'outdoor_classrooms': len(outdoor_classrooms) if outdoor_classrooms else 0,
            'indoor_count': indoor_count,
            'outdoor_count': outdoor_count
        }
        
    finally:
        db.disconnect()


def apply_solution_a():
    """应用方案A：在数据库中添加体育场地"""
    
    db_config = {
        "host": os.getenv("DB_HOST", "localhost"),
        "user": os.getenv("DB_USER", "root"),
        "password": os.getenv("DB_PASSWORD", "20051113Da"),
        "database": os.getenv("DB_NAME", "paike2"),
        "charset": "utf8mb4",
    }
    
    db = DatabaseConnector(**db_config)
    db.connect()
    
    try:
        cursor = db.connection.cursor()
        
        print("\n开始应用解决方案A...")
        print("-" * 80)
        
        # 1. 添加室外特征
        print("1. 添加/更新室外特征...")
        cursor.execute("""
            INSERT INTO classroom_features (feature_id, feature_name, description)
            VALUES ('SW', '室外', '室外场地') 
            ON DUPLICATE KEY UPDATE feature_name='室外'
        """)
        print("   ✓ 室外特征已添加/更新")
        
        # 2. 添加体育场地
        print("2. 添加体育场地...")
        try:
            cursor.execute("""
                INSERT INTO classrooms (classroom_id, classroom_name, building_name, campus_id, type, capacity, is_available)
                VALUES 
                ('SPORT_N', '北区体育场', '北区体育场', 'DB', '室外', 500, 1),
                ('SPORT_S', '南区体育场', '南区体育场', 'DB', '室外', 500, 1),
                ('GYM_1', '体育馆1', '体育馆', 'DB', '室内', 200, 1),
                ('GYM_2', '体育馆2', '体育馆', 'DB', '室内', 200, 1)
            """)
            print("   ✓ 体育场地已添加")
        except Exception as e:
            if "Duplicate entry" in str(e):
                print("   ℹ 体育场地已存在，跳过")
            else:
                raise
        
        # 3. 为体育场地添加特征
        print("3. 为体育场地添加室外特征...")
        try:
            cursor.execute("""
                INSERT INTO classroom_has_features (classroom_id, feature_id)
                VALUES 
                ('SPORT_N', 'SW'),
                ('SPORT_S', 'SW'),
                ('GYM_1', 'SW'),
                ('GYM_2', 'SW')
            """)
            print("   ✓ 体育场地特征已添加")
        except Exception as e:
            if "Duplicate entry" in str(e):
                print("   ℹ 体育场地特征已存在，跳过")
            else:
                raise
        
        # 4. 设置体育课程需要室外特征
        print("4. 设置体育课程需要室外场地...")
        try:
            cursor.execute("""
                INSERT INTO course_required_features (course_id, feature_id)
                VALUES 
                ('PHYE000111', 'SW'),
                ('PHYE000311', 'SW'),
                ('PHYE000511', 'SW')
                ON DUPLICATE KEY UPDATE feature_id=feature_id
            """)
            print("   ✓ 体育课程特征要求已设置")
        except Exception as e:
            print(f"   ⚠ 设置课程特征要求时出错: {e}")
            print("   ℹ 可能是 course_required_features 表不存在，需要手动创建")
        
        db.connection.commit()
        
        print("\n" + "=" * 80)
        print("✓ 解决方案A应用成功！")
        print("=" * 80)
        print("\n下一步操作：")
        print("1. 重新运行排课程序：python suan2.py --version 2")
        print("2. 或者调整现有排课：python analyze_conflicts.py <version_id>")
        
    except Exception as e:
        db.connection.rollback()
        print(f"\n✗ 应用解决方案失败: {e}")
        raise
    finally:
        cursor.close()
        db.disconnect()


if __name__ == "__main__":
    import sys
    
    # 诊断问题
    result = diagnose_pe_courses()
    
    # 询问是否应用解决方案
    if result['indoor_count'] > 0 or result['outdoor_classrooms'] == 0:
        print("\n" + "=" * 80)
        choice = input("\n是否立即应用解决方案A（添加体育场地）? (y/n): ").strip().lower()
        
        if choice == 'y':
            apply_solution_a()
        else:
            print("\n已取消。您可以稍后手动执行上述SQL语句。")
    else:
        print("\n✓ 体育课教室配置正常，无需修复。")
