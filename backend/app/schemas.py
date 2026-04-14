# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class RunCreate(BaseModel):
    task_type: str = Field(..., description="denoise/deblur/dehaze/sr/lowlight/video_denoise/video_sr")
    dataset_id: str
    algorithm_id: str
    params: Dict[str, Any] = Field(default_factory=dict)
    strict_validate: bool = False
    eval_mode: str = "preview"


class RunOut(BaseModel):
    run_id: str
    task_type: str
    dataset_id: str
    algorithm_id: str
    owner_id: Optional[str] = "system"
    strict_validate: bool = False
    record: Dict[str, Any] = Field(default_factory=dict)

    status: str  # queued/running/done/failed
    created_at: float
    started_at: Optional[float] = None
    finished_at: Optional[float] = None
    elapsed: Optional[float] = None

    metrics: Dict[str, Any] = Field(default_factory=dict)
    params: Dict[str, Any] = Field(default_factory=dict)
    samples: List[Dict[str, Any]] = Field(default_factory=list)
    error: Optional[str] = None
    error_code: Optional[str] = None
    error_detail: Optional[Dict[str, Any]] = None

class DatasetCreate(BaseModel):
    name: str
    type: str = "图像"
    size: str = "-"
    description: str = ""
    visibility: str = "private"
    allow_use: bool = False
    allow_download: bool = False
    # 算法任务维度：去噪/去雾/超分等；默认可空，扫描后由服务端写入或由用户 PATCH
    task_types: List[str] = Field(default_factory=list)


class DatasetPatch(BaseModel):
    name: Optional[str] = None
    type: Optional[str] = None
    size: Optional[str] = None
    description: Optional[str] = None
    visibility: Optional[str] = None
    allow_use: Optional[bool] = None
    allow_download: Optional[bool] = None
    task_types: Optional[List[str]] = None


class DatasetIdChange(BaseModel):
    new_dataset_id: str


class DatasetOut(BaseModel):
    dataset_id: str
    name: str
    type: str
    size: str
    description: str = ""
    download_count: int = 0
    owner_id: Optional[str] = "system"
    owner_display_name: str = ""
    source_owner_id: Optional[str] = None
    source_dataset_id: Optional[str] = None
    created_at: float
    meta: Dict[str, Any] = Field(default_factory=dict)
    visibility: str = "private"
    allow_use: bool = False
    allow_download: bool = False
    task_types: List[str] = Field(default_factory=list)


class DatasetImportZip(BaseModel):
    filename: str
    data_b64: str
    overwrite: bool = False


class AlgorithmCreate(BaseModel):
    task: str
    name: str
    impl: str = "OpenCV"
    version: str = "v1"
    description: str = ""
    default_params: Dict[str, Any] = Field(default_factory=dict)
    param_presets: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    visibility: str = "private"
    allow_use: bool = False
    allow_download: bool = False


class AlgorithmPatch(BaseModel):
    task: Optional[str] = None
    name: Optional[str] = None
    impl: Optional[str] = None
    version: Optional[str] = None
    description: Optional[str] = None
    default_params: Optional[Dict[str, Any]] = None
    param_presets: Optional[Dict[str, Dict[str, Any]]] = None
    visibility: Optional[str] = None
    allow_use: Optional[bool] = None
    allow_download: Optional[bool] = None


class AlgorithmOut(BaseModel):
    algorithm_id: str
    task: str
    name: str
    impl: str
    version: str
    description: str = ""
    dependency_text: str = ""
    entry_text: str = ""
    archive_filename: str = ""
    archive_sha256: str = ""
    source_submission_id: Optional[str] = None
    package_role: Optional[str] = None
    download_count: int = 0
    owner_id: Optional[str] = "system"
    owner_display_name: str = ""
    source_owner_id: Optional[str] = None
    source_algorithm_id: Optional[str] = None
    created_at: float
    default_params: Dict[str, Any] = Field(default_factory=dict)
    param_presets: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    visibility: str = "private"
    allow_use: bool = False
    allow_download: bool = False
    is_active: bool = True
    runtime_ready: bool = False


class ResourceCommentCreate(BaseModel):
    content: str


class ResourceCommentOut(BaseModel):
    comment_id: str
    resource_type: str
    resource_id: str
    author_id: str
    content: str
    created_at: float


class NoticeOut(BaseModel):
    notice_id: str
    username: str
    kind: str
    title: str
    content: str
    created_at: float
    read: bool = False


class ReportCreate(BaseModel):
    target_type: str
    target_id: str
    resource_type: Optional[str] = None
    resource_id: Optional[str] = None
    reason: str


class ReportOut(BaseModel):
    report_id: str
    target_type: str
    target_id: str
    resource_type: Optional[str] = None
    resource_id: Optional[str] = None
    reporter_id: str
    reason: str
    status: str = "pending"
    resolution: str = ""
    created_at: float
    resolved_at: Optional[float] = None
    resolved_by: Optional[str] = None


class ReportResolve(BaseModel):
    status: str = "resolved"
    resolution: str = ""


class PresetCreate(BaseModel):
    preset_id: Optional[str] = None
    name: str
    task_type: str
    dataset_id: str
    algorithm_id: str = ""
    algorithm_ids: List[str] = Field(default_factory=list)
    metrics: List[str] = Field(default_factory=list)
    params: Dict[str, Any] = Field(default_factory=dict)


class PresetPatch(BaseModel):
    name: Optional[str] = None
    task_type: Optional[str] = None
    dataset_id: Optional[str] = None
    algorithm_id: Optional[str] = None
    algorithm_ids: Optional[List[str]] = None
    metrics: Optional[List[str]] = None
    params: Optional[Dict[str, Any]] = None


class PresetOut(BaseModel):
    preset_id: str
    name: str
    task_type: str
    dataset_id: str
    algorithm_id: str
    algorithm_ids: List[str] = Field(default_factory=list)
    owner_id: Optional[str] = "system"
    metrics: List[str] = Field(default_factory=list)
    params: Dict[str, Any] = Field(default_factory=dict)
    created_at: float
    updated_at: float


class MetricCreate(BaseModel):
    metric_key: Optional[str] = None
    name: str
    display_name: Optional[str] = None
    description: str = ""
    task_types: List[str] = Field(default_factory=list)
    direction: str = "higher_better"
    requires_reference: bool = True
    implementation_type: str = "python"
    formula_text: str = ""
    code_text: str = ""
    code_filename: str = ""


class MetricPatch(BaseModel):
    metric_key: Optional[str] = None
    name: Optional[str] = None
    display_name: Optional[str] = None
    description: Optional[str] = None
    task_types: Optional[List[str]] = None
    direction: Optional[str] = None
    requires_reference: Optional[bool] = None
    implementation_type: Optional[str] = None
    formula_text: Optional[str] = None
    code_text: Optional[str] = None
    code_filename: Optional[str] = None


class MetricReview(BaseModel):
    status: str
    review_note: str = ""
    runtime_ready: bool = False


class MetricPublish(BaseModel):
    community_description: str = ""


class MetricOut(BaseModel):
    metric_id: str
    metric_key: str
    name: str
    display_name: str = ""
    description: str = ""
    task_types: List[str] = Field(default_factory=list)
    direction: str = "higher_better"
    requires_reference: bool = True
    implementation_type: str = "builtin"
    formula_text: str = ""
    code_text: str = ""
    code_filename: str = ""
    owner_id: Optional[str] = "system"
    owner_display_name: str = ""
    status: str = "approved"
    runtime_ready: bool = False
    review_note: str = ""
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[float] = None
    visibility: str = "private"
    allow_download: bool = False
    download_count: int = 0
    source_owner_id: Optional[str] = None
    source_metric_id: Optional[str] = None
    community_published_at: Optional[float] = None
    created_at: float


class AlgorithmSubmissionCreate(BaseModel):
    task_type: str
    name: str
    version: str = "v1"
    description: str = ""
    dependency_text: str = ""
    entry_text: str = ""
    archive_filename: str
    archive_b64: str


class AlgorithmSubmissionReview(BaseModel):
    status: str
    review_note: str = ""
    collect_to_platform: bool = False
    runtime_ready: bool = False


class AlgorithmSubmissionPublish(BaseModel):
    community_description: str = ""


class AlgorithmSubmissionOut(BaseModel):
    submission_id: str
    task_type: str
    task_label: str = ""
    name: str
    version: str = "v1"
    description: str = ""
    dependency_text: str = ""
    entry_text: str = ""
    archive_filename: str = ""
    archive_size: int = 0
    archive_sha256: str = ""
    owner_id: Optional[str] = "system"
    owner_display_name: str = ""
    status: str = "pending"
    review_note: str = ""
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[float] = None
    runtime_ready: bool = False
    created_at: float
    owner_algorithm_id: Optional[str] = None
    platform_algorithm_id: Optional[str] = None
    community_algorithm_id: Optional[str] = None
    community_published_at: Optional[float] = None


class UserCreate(BaseModel):
    username: str
    password: str


class UserOut(BaseModel):
    username: str
    display_name: str = ""
    role: str = "user"
    created_at: float


class UserPasswordChange(BaseModel):
    old_password: str
    new_password: str


class UserProfileUpdate(BaseModel):
    display_name: str


class Token(BaseModel):
    access_token: str
    token_type: str
    username: str
    display_name: str = ""
    role: str = "user"
