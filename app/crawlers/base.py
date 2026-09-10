from abc import ABC, abstractmethod

class BaseJobCrawler(ABC):
    """所有招聘网站爬虫的抽象基类"""
    @abstractmethod
    async def fetch_job_list(self, keyword: str, city: str, pages: int) -> list[dict]:
        """获取职位列表"""
        pass

    @abstractmethod
    async def fetch_job_detail(self, job_id: str) -> dict:
        """获取职位详情"""
        pass