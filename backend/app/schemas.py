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
    metrics: List[str] = Field(default_factory=list)
    params: Dict[str, Any] = Field(default_factory=dict)
    created_at: float
    updated_at: float
