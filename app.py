import sqlite3
import re
import json
import os
from db_operation import create_chroma_db, answer_without_chroma_db, answer_user_query
from visualization import create_heatmap, create_comparison_heatmap

# [1] rag准备

# 检查是否存在rag向量数据库
create_chroma_db("rag_shqp", "shqp_rag.txt")

def extract_scores_from_text(text):
    """Extract scores from the text using regex"""
    scores = {}
    # Match patterns like "xxx = xx" or "xxx=xx"
    pattern = r'(\w+)\s*=\s*(\d+)'
    matches = re.finditer(pattern, text)
    for match in matches:
        key = match.group(1)
        value = int(match.group(2))
        scores[key] = value
    return scores

def query_personality_score(user_id):
    """Query user personality scores from database"""
    conn = sqlite3.connect("user.db")
    c = conn.cursor()
    cursor = c.execute("SELECT * from personality where id = ?", (user_id,))
    columns = [description[0] for description in cursor.description]
    row = cursor.fetchone()
    conn.close()
    return row

def query_columns():
    """Query column names from database"""
    conn = sqlite3.connect("user.db")
    c = conn.cursor()
    cursor = c.execute("SELECT * from personality")
    columns = [description[0] for description in cursor.description]
    conn.close()
    return columns

def query_user_data(user_id):
    """查询用户的行为数据
    
    Args:
        user_id: 用户ID
        
    Returns:
        list: 用户行为数据列表
    """
    try:
        conn = sqlite3.connect("user.db")
        c = conn.cursor()
        cursor = c.execute("SELECT * FROM user_behavior WHERE user_id = ?", (user_id,))
        rows = cursor.fetchall()
        conn.close()
        return rows
    except Exception as e:
        print(f"Error querying user data: {str(e)}")
        return []

def analyze_user_behavior(user_data, initial_scores):
    """分析用户行为并更新性格分数
    
    Args:
        user_data: 用户行为数据
        initial_scores: 初始性格分数
        
    Returns:
        list: 更新后的性格分数
    """
    try:
        # 这里可以添加更复杂的行为分析逻辑
        # 目前简单返回初始分数
        return initial_scores
    except Exception as e:
        print(f"Error analyzing user behavior: {str(e)}")
        return initial_scores

def get_recommendations(scores):
    """根据性格分数获取推荐商品
    
    Args:
        scores: 性格分数列表
        
    Returns:
        list: 推荐商品列表
    """
    try:
        # 这里可以添加更复杂的推荐逻辑
        # 目前返回空列表
        return []
    except Exception as e:
        print(f"Error getting recommendations: {str(e)}")
        return []

def get_user_operations(user_id):
    """从JSON文件中获取指定用户的操作日志
    
    Args:
        user_id: 用户ID
        
    Returns:
        dict: 用户操作日志
    """
    try:
        # 读取JSON文件
        with open('user_operations.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # 过滤出指定用户的操作
        user_operations = [
            op for op in data['operations']
            if op['user_id'] == str(user_id)
        ]
        
        # 如果没有找到用户操作，返回空列表
        if not user_operations:
            return {"operations": []}
            
        # 返回用户操作日志
        return {"operations": user_operations}
        
    except Exception as e:
        print(f"Error reading user operations: {str(e)}")
        # 如果出错，返回空操作日志
        return {"operations": []}

def process_user_analysis(user_id):
    """Process user analysis and return results"""
    profile = query_personality_score(user_id)
    
    # Create initial personality scores dictionary
    initial_scores = {}
    for col, val in zip(query_columns(), profile):
        if col != 'id':  # Skip the id column
            initial_scores[col] = val
    
    # 获取用户特定的操作日志
    user_operation_diary = json.dumps(get_user_operations(user_id), ensure_ascii=False)
    
    # 构建用户画像字符串
    user_profile = f"用户的三魂六魄画像：id = {user_id}"
    for col, val in zip(query_columns(), profile):
        user_profile += f", {col} = {val}"
    user_profile += "."
    
    # 生成操作总结
    prompt_diary = "以上是该用户的操作日志，请按以下格式进行总结：'用户xx天内操作了xx次xx'...注意不要生成其他的信息，不需要解释你的回答。"
    result_summary = ''.join(answer_without_chroma_db(user_operation_diary + prompt_diary))
    
    # 生成新的画像
    prompt_profile = """
    请根据用户的操作日志，和旧的用户画像，覆盖用户画像分数。你必须严格按照参考内容的打分标准进行打分。
    输出格式为：用户的三魂七魄画像：\n
    id = xxx\n
    旧的xxx = xxx, 旧的xxx = xxx,
    新的xxx = xxx, 新的xxx = xxx,
    xxx变化了xxx分, xxx变化了xxx分.
    """
    
    result_profile = ''.join(
        answer_user_query("rag_shqp", 
                        "用户id：" + user_id + "\n用户画像：" + 
                        user_profile + result_summary + prompt_profile))
    
    # 提取新分数
    new_scores = extract_scores_from_text(result_profile)
    
    # 确保新分数包含所有原始特征
    for trait in initial_scores.keys():
        if trait not in new_scores:
            new_scores[trait] = initial_scores[trait]
    
    # 生成热力图
    create_heatmap(initial_scores, f"Initial Personality Heatmap for User {user_id}", 
                  f"initial_heatmap_{user_id}.png")
    create_heatmap(new_scores, f"Updated Personality Heatmap for User {user_id}", 
                  f"updated_heatmap_{user_id}.png")
    create_comparison_heatmap(initial_scores, new_scores, 
                            f"Personality Scores Comparison for User {user_id}",
                            f"comparison_heatmap_{user_id}.png")
    
    # 生成推荐列表
    recommended_projects = [
        "4K超高清智能电视",
        "节能型智能洗衣机",
        "多功能电动剃须刀",
        "有机冷压橄榄油",
        "智能跑步机",
        "环保材料制成的休闲鞋",
        "天然成分护肤套装",
        "教育互动机器人",
        "便携式太阳能帐篷灯",
        "可定制的智能壁挂画",
    ]
    
    prompt_item_list = "请根据用户的操作和画像，生成一个排好序的推荐列表，推荐列表中应该包含3个产品，每个产品的名称应该是一个字符串，输出格式为：产品1\n 产品2\n 产品3\n ..."
    
    result_item_list = ''.join(answer_without_chroma_db("用户画像："
                                                        + result_profile
                                                        + "待推荐的项目列表："
                                                        + str(recommended_projects)
                                                        + prompt_item_list))
    
    return {
        'summary': result_summary,
        'profile': result_profile,
        'recommendations': result_item_list,
        'images': {
            'initial': f"initial_heatmap_{user_id}.png",
            'updated': f"updated_heatmap_{user_id}.png",
            'comparison': f"comparison_heatmap_{user_id}.png"
        }
    }
