"""Word 生成器测试"""
from app.utils.docx_generator import generate_resume_docx


SAMPLE_DATA = {
    "name": "张三",
    "contact": "zhangsan@example.com | 138-0000-0000",
    "summary": "3 年 Python 后端开发经验，熟悉 FastAPI 和微服务架构。",
    "education": ["2017.09-2021.06  某大学  计算机本科"],
    "experience": [
        "2021.07-2024.07  某公司  后端开发工程师",
        "- 使用 Python + FastAPI 搭建微服务，接口响应时间降低 60%",
    ],
    "projects": ["智能招聘系统：基于 LangChain 实现简历解析和岗位匹配"],
    "skills": ["Python", "FastAPI", "MySQL", "Redis", "Docker"],
}


def test_generate_docx_returns_bytes():
    data = generate_resume_docx(SAMPLE_DATA, template="classic")
    assert isinstance(data, bytes)
    assert len(data) > 1000    # DOCX 至少有 1KB
    assert data[:2] == b"PK"   # ZIP 文件头（DOCX 是 ZIP）


def test_all_templates():
    """三个模板都应该能生成"""
    for tpl in ["classic", "modern", "minimal"]:
        data = generate_resume_docx(SAMPLE_DATA, template=tpl)
        assert isinstance(data, bytes)
        assert len(data) > 1000
        print(f"✓ {tpl}: {len(data)} bytes")


def test_empty_data():
    """空数据不应该崩溃"""
    data = generate_resume_docx({}, template="classic")
    assert isinstance(data, bytes)