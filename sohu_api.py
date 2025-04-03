import json
import os
from datetime import datetime
import requests
import sqlite3


class SohuGlobalAPI:
    def __init__(self, base_url):
        self.base_url = base_url
        self.access_token = None

    def login(self, phone, password, login_type="PASSWORD", user_name="admin"):
        """登录获取 access token

        Args:
            phone: 手机号/用户名
            password: 密码
            login_type: 登录类型，默认为 PASSWORD
            user_name: 用户名，默认为 admin

        Returns:
            bool: 登录是否成功
        """
        url = f"{self.base_url}/auth/v2/login"
        payload = {
            "phone": phone,
            "code": "",
            "loginType": login_type,
            "password": password,
            "userName": user_name
        }

        try:
            response = requests.post(url, json=payload)
            if response.status_code == 200:
                data = response.json()
                if data.get("code") == 200:
                    access_token = data["data"].get("accessToken")
                    if not access_token:
                        raise Exception("Login failed: accessToken is missing")
                    self.access_token = access_token
                    print("Successfully logged in to Sohu API")
                    return True
                else:
                    raise Exception(f"Login failed: {data.get('msg', 'Unknown error')}")
            else:
                raise Exception(f"Login failed with status code: {response.status_code}")
        except Exception as e:
            print(f"Error during login: {str(e)}")
            return False

    def get_headers(self):
        """获取请求头，包含 Authorization token

        Returns:
            dict: 请求头字典
        """
        if not self.access_token:
            raise Exception("Not authenticated")
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }

    def _get(self, endpoint, params):
        """发送 GET 请求

        Args:
            endpoint: API 端点
            params: 请求参数

        Returns:
            dict: 响应数据
        """
        url = f"{self.base_url}{endpoint}"
        headers = self.get_headers()
        try:
            response = requests.get(url, headers=headers, params=params, timeout=10)
            if response.status_code != 200:
                raise Exception(f"Request failed with status code {response.status_code}")
            return response.json()
        except requests.exceptions.RequestException as e:
            raise Exception(f"Network error occurred: {str(e)}")

    def _get_all_pages(self, endpoint, params):
        """获取所有页面的数据

        Args:
            endpoint: API 端点
            params: 请求参数

        Returns:
            dict: 包含所有数据的字典
        """
        all_data = []
        page_num = 1
        while True:
            params["pageNum"] = page_num
            response = self._get(endpoint, params)
            if response["code"] != 200:
                break
            data = response["data"]
            if not data:
                break
            all_data.extend(data)
            if len(data) < params["pageSize"]:
                break
            page_num += 1
        return {"total": len(all_data), "data": all_data}

    def get_audit_list(self, page_size=10, busy_type="Article", role_key="admin", **kwargs):
        """获取审核列表

        Args:
            page_size: 每页条数
            busy_type: 业务类型，默认为 Article
            role_key: 角色键，默认为 admin
            **kwargs: 其他参数

        Returns:
            dict: 审核列表数据
        """
        params = {
            "pageSize": page_size,
            "busyType": busy_type,
            "roleKey": role_key
        }
        params.update(kwargs)
        return self._get_all_pages("/admin/audit/list", params)

    def get_product_list(self, page_size=10, product_type=2):
        """获取商品列表

        Args:
            page_size: 每页条数
            product_type: 商品状态：出售中（1）、仓库中（2）、待审核（6）、审核未通过（7）

        Returns:
            dict: 商品列表数据
        """
        params = {
            "pageSize": page_size,
            "type": product_type
        }
        return self._get_all_pages("/shop-goods/product/pc/list", params)

    def get_article_list(self, state=None, page_size=10):
        """获取图文列表

        Args:
            state: 状态：已通过（OnShelf）、审核中（WaitApprove）、已拒绝（Refuse）、强制下架（CompelOff）
            page_size: 每页条数

        Returns:
            dict: 图文列表数据
        """
        return self.get_audit_list(page_size=page_size, state=state, busy_type="Article")

    def get_video_list(self, state=None, page_size=10):
        """获取视频列表

        Args:
            state: 状态：已通过（OnShelf）、审核中（WaitApprove）、已拒绝（Refuse）、强制下架（CompelOff）
            page_size: 每页条数

        Returns:
            dict: 视频列表数据
        """
        return self.get_audit_list(page_size=page_size, state=state, busy_type="Video")

    def get_comments(self, busy_code, busy_type, page_size=10):
        """获取评论列表

        Args:
            busy_code: 业务编码
            busy_type: 业务类型：图文（Article）、视频（Video）
            page_size: 每页条数

        Returns:
            dict: 评论列表数据
        """
        endpoint = "/app/api/common/comment/list"
        params = {
            "busyCode": busy_code,
            "busyType": busy_type,
            "pageSize": page_size
        }
        return self._get_all_pages(endpoint, params)

    def get_details(self, busy_code, busy_type):
        """获取内容详情

        Args:
            busy_code: 业务编码
            busy_type: 业务类型：Video、Article、Product

        Returns:
            dict: 内容详情数据
        """
        if busy_type == "Video":
            endpoint = f"/app/api/content/video/{busy_code}"
        elif busy_type == "Article":
            endpoint = f"/app/api/content/article/{busy_code}"
        elif busy_type == "Product":
            endpoint = f"/app/api/content/product/{busy_code}"
        else:
            raise ValueError("Invalid busy_type. Must be 'Video', 'Article', or 'Product'.")

        response = self._get(endpoint, {})
        if response["code"] != 200:
            raise Exception("Failed to get details")

        return response["data"]

    def get_playlet_list(self, page_size=10, state=None, **kwargs):
        """获取短剧列表

        Args:
            page_size: 每页条数
            state: 状态：已通过（OnShelf）、审核中（WaitApprove）、已拒绝（Refuse）、强制下架（CompelOff）
            **kwargs: 其他参数

        Returns:
            dict: 短剧列表数据
        """
        params = {
            "pageSize": page_size
        }
        if state:
            params["state"] = state
        params.update(kwargs)
        return self._get_all_pages("/admin/playlet/list", params)

    # 便捷方法
    def get_articles_on_shelf(self, page_size=10):
        """获取已上架的图文列表"""
        return self.get_article_list(state="OnShelf", page_size=page_size)

    def get_articles_waiting_approval(self, page_size=10):
        """获取待审核的图文列表"""
        return self.get_article_list(state="WaitApprove", page_size=page_size)

    def get_articles_rejected(self, page_size=10):
        """获取已拒绝的图文列表"""
        return self.get_article_list(state="Refuse", page_size=page_size)

    def get_articles_compelled_off(self, page_size=10):
        """获取强制下架的图文列表"""
        return self.get_article_list(state="CompelOff", page_size=page_size)

    def get_videos_on_shelf(self, page_size=10):
        """获取已上架的视频列表"""
        return self.get_video_list(state="OnShelf", page_size=page_size)

    def get_videos_waiting_approval(self, page_size=10):
        """获取待审核的视频列表"""
        return self.get_video_list(state="WaitApprove", page_size=page_size)

    def get_videos_rejected(self, page_size=10):
        """获取已拒绝的视频列表"""
        return self.get_video_list(state="Refuse", page_size=page_size)

    def get_videos_compelled_off(self, page_size=10):
        """获取强制下架的视频列表"""
        return self.get_video_list(state="CompelOff", page_size=page_size)

    def get_products_on_sale(self, page_size=10):
        """获取在售商品列表"""
        return self.get_product_list(page_size=page_size, product_type=1)

    def get_products_in_warehouse(self, page_size=10):
        """获取仓库中的商品列表"""
        return self.get_product_list(page_size=page_size, product_type=2)

    def get_products_pending_approval(self, page_size=10):
        """获取待审核的商品列表"""
        return self.get_product_list(page_size=page_size, product_type=6)

    def get_products_rejected(self, page_size=10):
        """获取审核未通过的商品列表"""
        return self.get_product_list(page_size=page_size, product_type=7)

    def get_playlets_on_shelf(self, page_size=10):
        """获取已上架的短剧列表"""
        return self.get_playlet_list(page_size=page_size, state="OnShelf")

    def get_playlets_waiting_approval(self, page_size=10):
        """获取待审核的短剧列表"""
        return self.get_playlet_list(page_size=page_size, state="WaitApprove")

    def get_playlets_rejected(self, page_size=10):
        """获取已拒绝的短剧列表"""
        return self.get_playlet_list(page_size=page_size, state="Refuse")

    def get_playlets_compelled_off(self, page_size=10):
        """获取强制下架的短剧列表"""
        return self.get_playlet_list(page_size=page_size, state="CompelOff")

    def get_product_categories(self):
        """获取商品分类列表

        Returns:
            dict: 包含分类数据的字典
        """
        try:
            # 从数据库获取分类数据
            with sqlite3.connect('user.db') as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT id, name, parent_id, level, sort_order 
                    FROM product_category 
                    WHERE status = 1 
                    ORDER BY level, sort_order
                """)
                categories = cursor.fetchall()

            # 构建分类树
            category_dict = {}
            for category in categories:
                category_dict[category[0]] = {
                    'id': category[0],
                    'name': category[1],
                    'parent_id': category[2],
                    'level': category[3],
                    'sort_order': category[4],
                    'children': []
                }

            # 构建树形结构
            root_categories = []
            for category_id, category in category_dict.items():
                if category['parent_id'] is None:
                    root_categories.append(category)
                else:
                    parent = category_dict.get(category['parent_id'])
                    if parent:
                        parent['children'].append(category)

            return {
                'code': 0,
                'message': 'success',
                'data': root_categories
            }
        except Exception as e:
            print(f"获取商品分类失败: {str(e)}")
            return {
                'code': 500,
                'message': f'获取商品分类失败: {str(e)}',
                'data': []
            }

    def get_products_by_category(self, category_id, page=1, page_size=10):
        """获取指定分类下的商品列表

        Args:
            category_id (int): 分类ID
            page (int): 页码
            page_size (int): 每页数量

        Returns:
            dict: 包含商品数据的字典
        """
        try:
            # 从数据库获取商品数据
            with sqlite3.connect('user.db') as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT p.id, p.name, p.description, p.price, p.image_url, p.status
                    FROM product p
                    JOIN product_category_relation pcr ON p.id = pcr.product_id
                    WHERE pcr.category_id = ? AND p.status = 1
                    LIMIT ? OFFSET ?
                """, (category_id, page_size, (page - 1) * page_size))
                products = cursor.fetchall()

            # 构建商品列表
            product_list = []
            for product in products:
                product_list.append({
                    'id': product[0],
                    'name': product[1],
                    'description': product[2],
                    'price': product[3],
                    'imageUrl': product[4],
                    'status': product[5]
                })

            return {
                'code': 0,
                'message': 'success',
                'data': product_list
            }
        except Exception as e:
            print(f"获取分类商品失败: {str(e)}")
            return {
                'code': 500,
                'message': f'获取分类商品失败: {str(e)}',
                'data': []
            }