from __future__ import annotations

import json
from pathlib import Path
import unittest

from pydantic import TypeAdapter

from app.schemas import (
    CreateSessionOut,
    CreateSessionRequest,
    MetadataOut,
    PracticePlanOut,
    QuestionListOut,
    RadarItemOut,
    ReportListItemOut,
    SessionDetailOut,
    SessionReportOut,
    WrongBookOut,
)


CONTRACT_DIR = Path(__file__).resolve().parents[2] / "contracts" / "api"


def load_contract(name: str) -> object:
    return json.loads((CONTRACT_DIR / name).read_text(encoding="utf-8"))


class ApiContractTest(unittest.TestCase):
    def test_question_contracts_match_backend_schemas(self) -> None:
        MetadataOut.model_validate(load_contract("metadata.json"))
        QuestionListOut.model_validate(load_contract("question-list.json"))

    def test_session_contracts_match_backend_schemas(self) -> None:
        CreateSessionRequest.model_validate(load_contract("create-session-request.json"))
        CreateSessionOut.model_validate(load_contract("create-session-response.json"))
        SessionDetailOut.model_validate(load_contract("session-detail.json"))

    def test_training_loop_contracts_match_backend_schemas(self) -> None:
        PracticePlanOut.model_validate(load_contract("practice-plan.json"))
        SessionReportOut.model_validate(load_contract("session-report.json"))
        TypeAdapter(list[ReportListItemOut]).validate_python(load_contract("reports.json"))
        TypeAdapter(list[RadarItemOut]).validate_python(load_contract("radar.json"))
        TypeAdapter(list[WrongBookOut]).validate_python(load_contract("wrong-book.json"))


if __name__ == "__main__":
    unittest.main()
