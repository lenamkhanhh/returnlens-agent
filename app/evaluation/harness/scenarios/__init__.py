"""Scenario registry for Card B11."""

from __future__ import annotations

from typing import Dict, Type

from app.evaluation.harness.scenarios.base import BaseScenario
from app.evaluation.harness.scenarios.s01_wismo import Scenario01Wismo
from app.evaluation.harness.scenarios.s02_wismo_counterfactual import Scenario02WismoCounterfactual
from app.evaluation.harness.scenarios.s03_damage_case_a import Scenario03DamageCaseA
from app.evaluation.harness.scenarios.s04_mismatch_case_b import Scenario04MismatchCaseB
from app.evaluation.harness.scenarios.s05_unclear_case_c import Scenario05UnclearCaseC
from app.evaluation.harness.scenarios.s06_late import Scenario06Late
from app.evaluation.harness.scenarios.s07_ndr import Scenario07Ndr
from app.evaluation.harness.scenarios.s08_voice_hindi import Scenario08VoiceHindi
from app.evaluation.harness.scenarios.s09_returning_restart import Scenario09ReturningRestart
from app.evaluation.harness.scenarios.s10_cumulative_split import Scenario10CumulativeSplit

ALL_SCENARIOS: Dict[str, Type[BaseScenario]] = {
    "S01": Scenario01Wismo,
    "S02": Scenario02WismoCounterfactual,
    "S03": Scenario03DamageCaseA,
    "S04": Scenario04MismatchCaseB,
    "S05": Scenario05UnclearCaseC,
    "S06": Scenario06Late,
    "S07": Scenario07Ndr,
    "S08": Scenario08VoiceHindi,
    "S09": Scenario09ReturningRestart,
    "S10": Scenario10CumulativeSplit,
}
