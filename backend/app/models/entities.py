from datetime import datetime

from sqlalchemy import JSON, DateTime, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class Resume(Base):
    __tablename__ = "resumes"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    filename: Mapped[str] = mapped_column(String(255))
    raw_text: Mapped[str] = mapped_column(Text)
    # 上传的原文件在 FILES_DIR 内的绝对路径（粘贴文本创建的简历为 NULL，仅文本预览）
    file_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    owner_id: Mapped[str] = mapped_column(String(64), default="local", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class ResumeVersion(Base):
    """M44 简历版本链：Resume.raw_text 的历史快照，支持任选两版 diff 对比。

    v1 在简历创建（上传/粘贴）时自动落；编辑器「保存到简历库」命中同名简历
    且文本有变化时追加新版本并更新 raw_text；每份简历上限 _VERSION_CAP 条，
    超出删最旧。
    """
    __tablename__ = "resume_versions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    resume_id: Mapped[int] = mapped_column(index=True)
    owner_id: Mapped[str] = mapped_column(String(64), default="local", index=True)
    content: Mapped[str] = mapped_column(Text)
    # initial 初始版本 / editor 编辑器保存 / manual 其他更新
    source: Mapped[str] = mapped_column(String(16), default="initial")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class DiagnosisRecord(Base):
    __tablename__ = "diagnosis_records"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    task_id: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    resume_id: Mapped[int | None] = mapped_column(nullable=True)
    resume_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    keyword: Mapped[str] = mapped_column(String(64), index=True)
    city: Mapped[str | None] = mapped_column(String(32), nullable=True)
    owner_id: Mapped[str] = mapped_column(String(64), default="local", index=True)
    status: Mapped[str] = mapped_column(String(16), default="running")
    # 进度快照（M6）：节流写入，服务重启后 /live/status 可回退 DB 读取
    stage: Mapped[str | None] = mapped_column(String(32), nullable=True)
    progress: Mapped[int | None] = mapped_column(nullable=True)
    logs: Mapped[list | None] = mapped_column(JSON, nullable=True)
    result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    # M16 跨重启恢复：waiting_clarify 任务的追问问题与恢复上下文落库
    questions: Mapped[list | None] = mapped_column(JSON, nullable=True)
    clarify_ctx: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # M20 重诊溯源：来源诊断任务 id（「用当前简历重新诊断」时记录，用于 Before/After 对比）
    parent_task_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class ExportHistory(Base):
    """导出历史：Word 导出动作记录（桌面形态含用户选择的保存路径，可再次定位文件）"""
    __tablename__ = "export_history"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    owner_id: Mapped[str] = mapped_column(String(64), default="local", index=True)
    filename: Mapped[str] = mapped_column(String(255))
    save_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    template: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Conversation(Base):
    """对话历史表：对答式优化 + 模拟面试共用"""
    __tablename__ = "conversations"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    task_id: Mapped[str] = mapped_column(String(32), index=True)
    type: Mapped[str] = mapped_column(String(16), index=True)         # optimize / interview
    owner_id: Mapped[str] = mapped_column(String(64), default="local", index=True)
    skill: Mapped[str | None] = mapped_column(String(16), nullable=True)
    # M31 独立面试会话上下文 JSON（resume_id/jd_text）；诊断内嵌面试不使用（走 DiagnosisRecord）
    context: Mapped[str | None] = mapped_column(Text, nullable=True)
    questions: Mapped[list] = mapped_column(JSON, default=list)
    answers: Mapped[dict] = mapped_column(JSON, default=dict)
    current_index: Mapped[int] = mapped_column(default=0)
    status: Mapped[str] = mapped_column(String(16), default="ongoing")  # ongoing / finished
    # M32 多轮自由对话完整记录：[{role: interviewer|candidate, qid, content}] 的 JSON 文本
    chat_log: Mapped[str | None] = mapped_column(Text, nullable=True)
    optimized_resume: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class AppSetting(Base):
    """M71 通用键值设置（owner+key 唯一）：导出根目录等用户级配置，为 M67 目标画像铺路。

    新表由 Base.metadata.create_all 建全，无需登记 ensure_schema_columns。
    """
    __tablename__ = "app_settings"
    __table_args__ = (
        UniqueConstraint("owner_id", "key", name="uq_app_settings_owner_key"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    owner_id: Mapped[str] = mapped_column(String(64), default="local", index=True)
    key: Mapped[str] = mapped_column(String(64))
    value: Mapped[str] = mapped_column(Text, default="")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class SavedJob(Base):
    """M45 岗位库：用户统一管理的心仪岗位（手动录入 / 岗位面板一键入库）。

    与 localStorage 收藏的区别：落库持久化、跨会话可批量与简历匹配推荐。
    """
    __tablename__ = "saved_jobs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    owner_id: Mapped[str] = mapped_column(String(64), default="local", index=True)
    title: Mapped[str] = mapped_column(String(80))
    company: Mapped[str] = mapped_column(String(60), default="")
    city: Mapped[str] = mapped_column(String(20), default="")
    salary: Mapped[str] = mapped_column(String(40), default="")
    jd_text: Mapped[str] = mapped_column(Text, default="")
    # manual 手动添加 / ai 岗位面板入库
    source: Mapped[str] = mapped_column(String(16), default="manual")
    # M49 投递状态：wish 想投 / applied 已投递 / interviewing 面试中 / offer / closed
    status: Mapped[str] = mapped_column(String(16), default="wish")
    # M56.4 投递台账：投递渠道 boss/zhilian/liepin/nowcoder/email/other + 首次投递时间
    apply_channel: Mapped[str | None] = mapped_column(String(16), default=None)
    apply_at: Mapped[datetime | None] = mapped_column(DateTime, default=None)
    # D2 版本赛马：首次标记已投递时关联的简历版本（空 = 未记录；不随重复标记覆盖）
    apply_resume_id: Mapped[int | None] = mapped_column(Integer, default=None)
    # M60 面试日程：用户在编辑弹窗自行维护的下次面试时间（空 = 无安排）
    next_interview_at: Mapped[datetime | None] = mapped_column(DateTime, default=None)
    url: Mapped[str] = mapped_column(String(300), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class StarCard(Base):
    """M65 项目素材库（STAR 卡片）：项目/成就统一建档（情境-任务-行动-结果）。

    一站式素材中枢，后续简历优化 / 面试答题 / 求职信生成将复用引用；本版仅档案本体。
    新表由 Base.metadata.create_all 建全，无需登记 ensure_schema_columns。
    """
    __tablename__ = "star_cards"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    owner_id: Mapped[str] = mapped_column(String(64), default="local", index=True)
    title: Mapped[str] = mapped_column(String(60))
    role: Mapped[str] = mapped_column(String(40), default="")
    # 逗号分隔的技术栈/能力标签
    tags: Mapped[str] = mapped_column(String(200), default="")
    situation: Mapped[str] = mapped_column(Text, default="")
    task: Mapped[str] = mapped_column(Text, default="")
    action: Mapped[str] = mapped_column(Text, default="")
    result: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class Offer(Base):
    """M62 Offer 比较决策器：手握多个 Offer 时的加权量化对比档案。

    评分/结论全部本地确定性计算（零 LLM 调用，红线=不编造）；
    新表由 Base.metadata.create_all 建全，无需登记 ensure_schema_columns。
    """
    __tablename__ = "offers"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    owner_id: Mapped[str] = mapped_column(String(64), default="local", index=True)
    company: Mapped[str] = mapped_column(String(60))
    title: Mapped[str] = mapped_column(String(60))
    city: Mapped[str] = mapped_column(String(20), default="")
    # 月薪，单位 K 元；年薪包 = monthly_salary * salary_months
    monthly_salary: Mapped[int] = mapped_column()
    # 年薪含几个月（12~18）
    salary_months: Mapped[int] = mapped_column(default=12)
    commute_minutes: Mapped[int] = mapped_column(default=45)
    # 五险一金缴纳诚意自评 1=最低 5=全额顶格
    insurance: Mapped[int] = mapped_column(default=3)
    development: Mapped[int] = mapped_column(default=3)
    stability: Mapped[int] = mapped_column(default=3)
    notes: Mapped[str] = mapped_column(String(500), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )
