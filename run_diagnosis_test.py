import asyncio
import json

from app.services.diagnosis_service import DiagnosisService


RESUME = """
个人简历
姓名：张三    学历：本科    工作年限：3年
技能：Python, FastAPI, Django, MySQL, Redis, Docker, Linux, Git

工作经历：
2021.07 - 2024.07  某互联网公司  后端开发工程师
- 负责核心业务系统后端开发，使用 Python + FastAPI 搭建微服务
- 优化数据库查询，引入 Redis 缓存，接口响应时间降低 60%
- 参与爬虫系统开发，抓取百万级数据并清洗入库
"""

JD = """
岗位：Python 后端开发工程师
要求：
- 3 年以上 Python 后端开发经验
- 熟练掌握 FastAPI/Django/Flask 至少一种框架
- 熟悉 MySQL、Redis，了解常见性能优化手段
- 有大规模数据处理经验者优先
- 有 AI/LLM 应用开发经验者优先
"""


async def main():
    service = DiagnosisService()
    print("开始多智能体诊断（约 30-60 秒）...\n")
    result = await service.diagnose(RESUME, JD)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())