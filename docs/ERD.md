# Algo Benchmark Platform ER 图（当前 SQL 存储）

> 说明：
> - 该图基于 `backend/app/sql_store.py` 的当前建表定义整理。
> - 当前库中大多是“逻辑关联”（通过 `*_id` 关联），不是数据库层面的外键约束。
> - 大部分实体完整 JSON 都放在 `payload_json` 字段中，表内其它列主要用于检索/筛选/排序。

```mermaid
erDiagram
    abp_users {
        string username PK
        string role
        string owner_id
        string visibility
        float created_at
        float updated_at
        float sort_at
        text payload_json
    }

    abp_algorithms {
        string algorithm_id PK
        string owner_id
        string task
        string name
        string impl
        string visibility
        string package_role
        string source_submission_id
        string source_owner_id
        string source_algorithm_id
        bool allow_use
        bool allow_download
        bool is_active
        bool runtime_ready
        float created_at
        float updated_at
        text payload_json
    }

    abp_algorithm_submissions {
        string submission_id PK
        string owner_id
        string task_type
        string name
        string status
        bool runtime_ready
        string owner_algorithm_id
        string community_algorithm_id
        string platform_algorithm_id
        float created_at
        float reviewed_at
        text payload_json
    }

    abp_algorithm_history {
        string history_id PK
        string submission_id
        string task_type
        string name
        string owner_id
        string visibility
        float created_at
        float updated_at
        float sort_at
        text payload_json
    }

    abp_datasets {
        string dataset_id PK
        string name
        string task_type
        string data_type
        string owner_id
        string visibility
        float created_at
        float updated_at
        float sort_at
        text payload_json
    }

    abp_runs {
        string run_id PK
        string status
        string task_type
        string dataset_id
        string owner_id
        string visibility
        float created_at
        float updated_at
        float sort_at
        text payload_json
    }

    abp_presets {
        string preset_id PK
        string name
        string task_type
        string dataset_id
        string algorithm_id
        string owner_id
        string visibility
        float created_at
        float updated_at
        float sort_at
        text payload_json
    }

    abp_metrics {
        string metric_id PK
        string metric_key
        string name
        string status
        string owner_id
        string visibility
        float created_at
        float updated_at
        float sort_at
        text payload_json
    }

    abp_metric_history {
        string history_id PK
        string metric_id
        string metric_key
        string name
        string owner_id
        string visibility
        float created_at
        float updated_at
        float sort_at
        text payload_json
    }

    abp_comments {
        string comment_record_id PK
        string comment_id
        string resource_type
        string resource_id
        string author_id
        string owner_id
        string visibility
        float created_at
        float updated_at
        float sort_at
        text payload_json
    }

    abp_reports {
        string report_id PK
        string reporter_id
        string target_type
        string status
        string owner_id
        string visibility
        float created_at
        float updated_at
        float sort_at
        text payload_json
    }

    abp_notices {
        string notice_record_id PK
        string notice_id
        string username
        string kind
        bool read
        string owner_id
        string visibility
        float created_at
        float updated_at
        float sort_at
        text payload_json
    }

    abp_store_records {
        string record_type PK
        string record_id PK
        string owner_id
        string visibility
        float created_at
        float updated_at
        float sort_at
        text payload_json
    }

    abp_users ||--o{ abp_algorithms : "owner_id"
    abp_users ||--o{ abp_algorithm_submissions : "owner_id"
    abp_users ||--o{ abp_datasets : "owner_id"
    abp_users ||--o{ abp_runs : "owner_id"
    abp_users ||--o{ abp_presets : "owner_id"
    abp_users ||--o{ abp_metrics : "owner_id"
    abp_users ||--o{ abp_comments : "author_id"
    abp_users ||--o{ abp_reports : "reporter_id"
    abp_users ||--o{ abp_notices : "username"

    abp_algorithms ||--o{ abp_runs : "algorithm_id(在payload_json中)"
    abp_datasets ||--o{ abp_runs : "dataset_id"

    abp_algorithms ||--o{ abp_presets : "algorithm_id"
    abp_datasets ||--o{ abp_presets : "dataset_id"

    abp_algorithm_submissions ||--o{ abp_algorithm_history : "submission_id"
    abp_algorithm_submissions ||--o{ abp_algorithms : "source_submission_id"

    abp_metrics ||--o{ abp_metric_history : "metric_id"

    abp_algorithms ||--o{ abp_comments : "resource_type=algorithm, resource_id"
    abp_datasets ||--o{ abp_comments : "resource_type=dataset, resource_id"

    abp_algorithms ||--o{ abp_reports : "target_type=algorithm, target_id"
    abp_datasets ||--o{ abp_reports : "target_type=dataset, target_id"
    abp_comments ||--o{ abp_reports : "target_type=comment, target_id"
```

