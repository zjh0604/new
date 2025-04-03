from flask import Flask, render_template, request, jsonify, send_from_directory
import os
from app import process_user_analysis, query_personality_score, query_columns
from db_operation import create_chroma_db
import socket
import logging
import sqlite3
import json

# 配置日志
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# 确保输出目录存在
if not os.path.exists('output'):
    os.makedirs('output')

# 检查是否存在rag向量数据库
create_chroma_db("rag_shqp", "shqp_rag.txt")

def init_database():
    """初始化数据库表"""
    try:
        conn = sqlite3.connect("user.db")
        c = conn.cursor()
        
        # 创建商品分类表
        c.execute('''
            CREATE TABLE IF NOT EXISTS product_category (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pid INTEGER DEFAULT 0,
                name TEXT,
                icon TEXT,
                level INTEGER DEFAULT 1,
                sort INTEGER DEFAULT 999,
                is_show INTEGER DEFAULT 1,
                is_del INTEGER DEFAULT 0,
                create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                update_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                sys_source TEXT DEFAULT 'sohuglobal'
            )
        ''')
        
        # 检查是否有数据
        c.execute("SELECT COUNT(*) FROM product_category")
        if c.fetchone()[0] == 0:
            # 插入一些初始分类
            categories = [
                (0, '饮品', 'https://sohugloba.oss-cn-beijing.aliyuncs.com/2023/09/20/e948541315a74d1f96e0f57ee79e867b.png', 1, 1, 1, 0),
                (0, '食品', 'https://sohugloba.oss-cn-beijing.aliyuncs.com/2023/09/20/food.png', 1, 2, 1, 0),
                (0, '电子产品', 'https://sohugloba.oss-cn-beijing.aliyuncs.com/2023/09/20/electronics.png', 1, 3, 1, 0),
                (0, '服装', 'https://sohugloba.oss-cn-beijing.aliyuncs.com/2023/09/20/clothing.png', 1, 4, 1, 0),
                (0, '家居', 'https://sohugloba.oss-cn-beijing.aliyuncs.com/2023/09/20/home.png', 1, 5, 1, 0)
            ]
            c.executemany("""
                INSERT INTO product_category (pid, name, icon, level, sort, is_show, is_del)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, categories)
        
        conn.commit()
        conn.close()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Error initializing database: {str(e)}")

# 在应用启动时初始化数据库
init_database()

@app.route('/')
def index():
    logger.debug("Accessing index page")
    return render_template('index.html')

@app.route('/users')
def user_management():
    logger.debug("Accessing user management page")
    try:
        # 连接数据库
        conn = sqlite3.connect("user.db")
        c = conn.cursor()
        # 查询所有用户ID
        cursor = c.execute("SELECT DISTINCT id FROM personality")
        user_ids = [row[0] for row in cursor.fetchall()]
        conn.close()
        return render_template('users.html', user_ids=user_ids)
    except Exception as e:
        logger.error(f"Error accessing user management: {str(e)}")
        return render_template('users.html', user_ids=[], error=str(e))

@app.route('/analyze', methods=['POST'])
def analyze():
    try:
        # 获取JSON数据
        data = request.get_json()
        user_id = data.get('user_id')
        
        if not user_id:
            logger.error("No user_id provided in request")
            return jsonify({
                'success': False,
                'error': '请提供用户ID'
            })
            
        logger.debug(f"Processing analysis for user_id: {user_id}")
        
        # 处理用户分析
        results = process_user_analysis(user_id)
        return jsonify({
            'success': True,
            **results
        })
        
    except Exception as e:
        logger.error(f"Error processing analysis: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        })

@app.route('/output/<path:filename>')
def serve_image(filename):
    logger.debug(f"Serving image: {filename}")
    return send_from_directory('output', filename)

@app.route('/get_personality/<user_id>')
def get_personality(user_id):
    logger.debug(f"Getting personality data for user_id: {user_id}")
    try:
        # 连接数据库
        conn = sqlite3.connect("user.db")
        c = conn.cursor()
        
        # 查询用户性格数据
        cursor = c.execute("SELECT * FROM personality WHERE id = ?", (user_id,))
        columns = [description[0] for description in cursor.description]
        row = cursor.fetchone()
        
        if row:
            # 创建特征和分数的字典，过滤掉None值
            personality_data = {}
            for col, val in zip(columns[1:], row[1:]):  # 跳过id列
                if val is not None:  # 只添加非None值
                    personality_data[col] = val
            
            if personality_data:  # 确保有数据
                # 按分数排序并获取前10个特征
                sorted_traits = sorted(personality_data.items(), key=lambda x: x[1], reverse=True)
                top_traits = sorted_traits[:10]
                
                # 分离特征名和分数
                traits = [trait for trait, _ in top_traits]
                scores = [score for _, score in top_traits]
                
                return jsonify({
                    'success': True,
                    'traits': traits,
                    'scores': scores
                })
            else:
                return jsonify({
                    'success': False,
                    'error': '用户性格数据为空'
                })
        else:
            return jsonify({
                'success': False,
                'error': '用户不存在'
            })
            
    except Exception as e:
        logger.error(f"Error getting personality data: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        })
    finally:
        conn.close()

@app.route('/get_recent_changes/<user_id>')
def get_recent_changes(user_id):
    logger.debug(f"Getting recent changes for user_id: {user_id}")
    try:
        # 首先尝试从数据库获取数据
        conn = sqlite3.connect("user.db")
        c = conn.cursor()
        
        try:
            # 查询用户操作日志
            cursor = c.execute("""
                SELECT operation_type, operation_time, details 
                FROM user_behavior 
                WHERE user_id = ? 
                ORDER BY operation_time DESC 
                LIMIT 10
            """, (user_id,))
            operations = cursor.fetchall()
            
            # 查询用户性格变化
            cursor = c.execute("""
                SELECT trait_name, old_value, new_value, change_time 
                FROM personality_changes 
                WHERE user_id = ? 
                ORDER BY change_time DESC 
                LIMIT 10
            """, (user_id,))
            changes = cursor.fetchall()
            
            if operations or changes:
                # 格式化操作日志
                formatted_operations = []
                for op in operations:
                    formatted_operations.append({
                        'type': op[0],
                        'time': op[1],
                        'details': op[2]
                    })
                
                # 格式化性格变化
                formatted_changes = []
                for change in changes:
                    formatted_changes.append({
                        'trait': change[0],
                        'old_value': change[1],
                        'new_value': change[2],
                        'time': change[3]
                    })
                
                return jsonify({
                    'success': True,
                    'has_data': True,
                    'operations': formatted_operations,
                    'changes': formatted_changes
                })
                
        except sqlite3.OperationalError:
            # 如果表不存在，从JSON文件获取数据
            logger.info(f"Database tables not found, using JSON file for user {user_id}")
            
            # 读取JSON文件
            with open('user_operations.json', 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # 过滤出指定用户的操作
            user_operations = [
                op for op in data['operations']
                if op['user_id'] == str(user_id)
            ]
            
            if user_operations:
                # 格式化操作日志
                formatted_operations = []
                for op in user_operations:
                    formatted_operations.append({
                        'type': op['action'],
                        'time': op['time'],
                        'details': op['detail']
                    })
                
                return jsonify({
                    'success': True,
                    'has_data': True,
                    'operations': formatted_operations,
                    'changes': []  # JSON文件中没有性格变化数据
                })
            
        # 如果没有找到任何数据
        return jsonify({
            'success': True,
            'has_data': False,
            'message': '暂无用户操作记录和性格变化数据'
        })
            
    except Exception as e:
        logger.error(f"Error getting recent changes: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        })
    finally:
        conn.close()

def get_server_info():
    try:
        hostname = socket.gethostname()
        local_ip = socket.gethostbyname(hostname)
        return hostname, local_ip
    except Exception as e:
        logger.error(f"Error getting server info: {str(e)}")
        return "unknown", "unknown"

if __name__ == '__main__':
    try:
        # 获取本机IP地址
        hostname, local_ip = get_server_info()
        
        print("\n=== Server Information ===")
        print(f"Hostname: {hostname}")
        print(f"Local IP address: {local_ip}")
        print("\n=== Available URLs ===")
        print(f"  - http://localhost:8080")
        print(f"  - http://127.0.0.1:8080")
        print(f"  - http://{local_ip}:8080")
        print("\nStarting server...")
        
        # 使用0.0.0.0作为host，允许所有网络接口的连接
        app.run(debug=True, host='0.0.0.0', port=8080, threaded=True)
    except Exception as e:
        logger.error(f"Failed to start server: {str(e)}")
        raise 