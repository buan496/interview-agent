# Staging Deployment Drill Evidence Template

Keep completed evidence outside this repository if it contains internal URLs, server details, operator names or environment-specific information.

Do not paste secrets, tokens, verification codes, full phone numbers, prompt text, completion text, raw user answer text, database passwords, API keys, private server IPs or private domains into this file.

## Drill Metadata

- drill_id:
- environment:
- operator:
- started_at:
- finished_at:
- commit_sha:
- image_tag:
- server_type:
- base_url:
- api_base_url:
- compose_files:
- env_file_location:

## Deployment Evidence

- code_checkout_result:
- compose_config_result:
- image_pull_or_build_result:
- stack_start_result:
- service_status:
- migration_result:
- alembic_revision:

## Health and Smoke Evidence

- health_result:
- ready_result:
- observed_request_id:
- smoke_result:
- frontend_login_result:
- auth_code_path_result:
- worker_check_result:

## Metrics and Alert Evidence

- metrics_result:
- metrics_access_control_result:
- alert_rules_check_result:
- active_p0_p1_incident_check:

## Backup and Restore Evidence

- backup_file:
- backup_size:
- backup_sha256:
- backup_verify_result:
- restore_drill_result:
- restore_target:
- restore_approval:
- backup_retention_note:

## Privacy Evidence

- data_summary_check_result:
- data_export_check_result:
- data_export_redaction_result:
- data_deletion_request_result:
- data_delete_confirm_result:
- backup_residue_note:

## LLM Gateway Evidence

- llm_gateway_enabled:
- primary_route:
- fallback_enabled:
- fallback_route:
- mock_eval_result:
- model_comparison_result:
- timeout_seconds:
- max_retries:
- usage_metering_check:
- cost_quota_check:

## Incident Evidence

- incident_template_check:
- incident_owner:
- rollback_owner:
- database_restore_approver:
- request_ids_recorded:

## Decision

- go_no_go_decision:
- decision_owner:
- known_risks:
- accepted_risks:
- blocking_issues:
- follow_up_tasks:
