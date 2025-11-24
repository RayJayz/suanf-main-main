-- ========================================
-- 体育课教室问题完整解决方案 SQL
-- ========================================
-- 问题：体育课应该在室外场地（体育场/体育馆）上课，但当前被分配到普通教室
-- 
-- 执行方式：
-- mysql -u root -p paike2 < fix_pe_courses.sql
-- 或者在MySQL客户端中逐条执行
-- ========================================

USE paike2;

-- ========================================
-- 步骤1: 确保室外特征存在
-- ========================================
INSERT INTO classroom_features (feature_id, feature_name, description)
VALUES ('SW', '室外', '室外场地，包括体育场和体育馆') 
ON DUPLICATE KEY UPDATE 
    feature_name = '室外',
    description = '室外场地，包括体育场和体育馆';

SELECT '✓ 步骤1完成: 室外特征已添加/更新' AS status;

-- ========================================
-- 步骤2: 添加体育场地（北区体育场、南区体育场、体育馆）
-- ========================================
INSERT INTO classrooms (classroom_id, classroom_name, building_name, campus_id, type, capacity, is_available, created_at, updated_at)
VALUES 
    ('SPORT_N', '北区体育场', '北区体育场', 'DB', '室外', 500, 1, NOW(), NOW()),
    ('SPORT_S', '南区体育场', '南区体育场', 'DB', '室外', 500, 1, NOW(), NOW()),
    ('GYM_1', '体育馆1', '体育馆', 'DB', '体育馆', 200, 1, NOW(), NOW()),
    ('GYM_2', '体育馆2', '体育馆', 'DB', '体育馆', 200, 1, NOW(), NOW())
ON DUPLICATE KEY UPDATE 
    classroom_name = VALUES(classroom_name),
    capacity = VALUES(capacity),
    updated_at = NOW();

SELECT '✓ 步骤2完成: 体育场地已添加' AS status;

-- ========================================
-- 步骤3: 为体育场地添加室外特征标记
-- ========================================
INSERT INTO classroom_has_features (classroom_id, feature_id)
VALUES 
    ('SPORT_N', 'SW'),
    ('SPORT_S', 'SW'),
    ('GYM_1', 'SW'),
    ('GYM_2', 'SW')
ON DUPLICATE KEY UPDATE feature_id = feature_id;

SELECT '✓ 步骤3完成: 体育场地特征已设置' AS status;

-- ========================================
-- 步骤4: 检查是否存在 course_required_features 表
-- 如果不存在，先创建该表
-- ========================================
CREATE TABLE IF NOT EXISTS course_required_features (
    course_id VARCHAR(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
    feature_id VARCHAR(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
    is_mandatory TINYINT(1) DEFAULT 1 COMMENT '1=必须, 0=优先',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (course_id, feature_id),
    FOREIGN KEY (course_id) REFERENCES courses(course_id) ON DELETE CASCADE ON UPDATE CASCADE,
    FOREIGN KEY (feature_id) REFERENCES classroom_features(feature_id) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='课程对教室特征的要求';

SELECT '✓ 步骤4完成: course_required_features 表已创建/已存在' AS status;

-- ========================================
-- 步骤5: 设置体育课程必须在室外场地上课
-- ========================================
INSERT INTO course_required_features (course_id, feature_id, is_mandatory)
VALUES 
    ('PHYE000111', 'SW', 1),  -- 体育Ⅰ
    ('PHYE000311', 'SW', 1),  -- 体育Ⅲ
    ('PHYE000511', 'SW', 1)   -- 体育健康课程Ⅰ
ON DUPLICATE KEY UPDATE 
    is_mandatory = 1,
    updated_at = NOW();

SELECT '✓ 步骤5完成: 体育课程特征要求已设置' AS status;

-- ========================================
-- 步骤6: 查看当前体育课的教室分配情况
-- ========================================
SELECT 
    '当前体育课教室分配情况' AS info,
    c.course_name AS '课程',
    cr.classroom_name AS '教室',
    cr.building_name AS '教学楼',
    cr.type AS '类型',
    cr.capacity AS '容量',
    GROUP_CONCAT(DISTINCT cf.feature_name SEPARATOR ', ') AS '特征',
    COUNT(DISTINCT s.schedule_id) AS '排课次数'
FROM courses c
JOIN course_offerings co ON c.course_id = co.course_id
JOIN teaching_tasks tt ON co.offering_id = tt.offering_id
JOIN schedules s ON tt.task_id = s.task_id
JOIN classrooms cr ON s.classroom_id = cr.classroom_id
LEFT JOIN classroom_has_features chf ON cr.classroom_id = chf.classroom_id
LEFT JOIN classroom_features cf ON chf.feature_id = cf.feature_id
WHERE c.course_id LIKE 'PHYE%'
GROUP BY c.course_name, cr.classroom_name, cr.building_name, cr.type, cr.capacity
ORDER BY c.course_name, cr.classroom_name;

-- ========================================
-- 步骤7: 查看新添加的体育场地
-- ========================================
SELECT 
    '新添加的体育场地' AS info,
    c.classroom_id AS '编号',
    c.classroom_name AS '名称',
    c.building_name AS '位置',
    c.type AS '类型',
    c.capacity AS '容量',
    GROUP_CONCAT(cf.feature_name SEPARATOR ', ') AS '特征'
FROM classrooms c
LEFT JOIN classroom_has_features chf ON c.classroom_id = chf.classroom_id
LEFT JOIN classroom_features cf ON chf.feature_id = cf.feature_id
WHERE c.classroom_id IN ('SPORT_N', 'SPORT_S', 'GYM_1', 'GYM_2')
GROUP BY c.classroom_id, c.classroom_name, c.building_name, c.type, c.capacity;

-- ========================================
-- 完成提示
-- ========================================
SELECT 
    '========================================' AS ' ',
    '✓ 体育场地设置完成！' AS '状态',
    '下一步请重新运行排课程序或调整现有排课' AS '建议';
