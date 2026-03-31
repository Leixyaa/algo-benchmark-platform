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
    dataset_id: Optional[str] = None
    name: str
    type: str = "图像"
    size: str = "-"


class DatasetPatch(BaseModel):
    name: Optional[str] = None
    type: Optional[str] = None
    size: Optional[str] = None


class DatasetOut(BaseModel):
    dataset_id: str
    name: str
    type: str
    size: str
    owner_id: Optional[str] = "system"
    created_at: float
    meta: Dict[str, Any] = Field(default_factory=dict)


class DatasetImportZip(BaseModel):
    filename: str
    data_b64: str
    overwrite: bool = False


class AlgorithmCreate(BaseModel):
    algorithm_id: Optional[str] = None
    task: str
    name: str
    impl: str = "OpenCV"
    version: str = "v1"
    default_params: Dict[str, Any] = Field(default_factory=dict)
    param_presets: Dict[str, Dict[str, Any]] = Field(default_factory=dict)


class AlgorithmPatch(BaseModel):
    task: Optional[str] = None
    name: Optional[str] = None
    impl: Optional[str] = None
    version: Optional[str] = None
    default_params: Optional[Dict[str, Any]] = None
    param_presets: Optional[Dict[str, Dict[str, Any]]] = None


class AlgorithmOut(BaseModel):
    algorithm_id: str
    task: str
    name: str
    impl: str
    version: str
    owner_id: Optional[str] = "system"
    created_at: float
    default_params: Dict[str, Any] = Field(default_factory=dict)
    param_presets: Dict[str, Dict[str, Any]] = Field(default_factory=dict)


class PresetCreate(BaseModel):
    preset_id: Optional[str] = None
    name: str
    task_type: str
    dataset_id: str
    algorithm_id: str
    metrics: List[str] = Field(default_factory=list)
    params: Dict[str, Any] = Field(default_factory=dict)


class PresetPatch(BaseModel):
    name: Optional[str] = None
    task_type: Optional[str] = None
    dataset_id: Optional[str] = None
    algorithm_id: Optional[str] = None
    metrics: Optional[List[str]] = None
    params: Optional[Dict[str, Any]] = None


class PresetOut(BaseModel):
    preset_id: str
    name: str
    task_type: str
    dataset_id: str
    algorithm_id: str
    owner_id: Optional[str] = "system"
    metrics: List[str] = Field(default_factory=list)
    params: Dict[str, Any] = Field(default_factory=dict)
    created_at: float
    updated_at: float


class FastSelectRequest(BaseModel):
    task_type: str = Field(..., description="denoise/deblur/dehaze/sr/lowlight/video_denoise/video_sr")
    dataset_id: str
    candidate_algorithm_ids: List[str] = Field(default_factory=list)
    top_k: int = 3
    alpha: float = 0.35
    lambda_reg: float = 1.0
    recency_half_life_hours: float = 72.0
    cold_start_bonus: float = 0.08
    low_support_penalty: float = 0.06
    min_support: int = 3


class FastSelectItem(BaseModel):
    algorithm_id: str
    score: float
    expected_reward: float = 0.0
    mean_reward: float
    uncertainty: float
    exploration_bonus: float = 0.0
    cold_start_bonus: float = 0.0
    reliability: float = 0.0
    sample_count: int


class FastSelectResponse(BaseModel):
    task_type: str
    dataset_id: str
    top_k: int
    reward_formula: str
    context: Dict[str, Any] = Field(default_factory=dict)
    recommendations: List[FastSelectItem] = Field(default_factory=list)


class UserCreate(BaseModel):
    username: str
    password: str


class UserOut(BaseModel):
    username: str
    created_at: float


class Token(BaseModel):
    access_token: str
    token_type: str
    username: str
