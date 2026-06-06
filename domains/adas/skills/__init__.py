"""
ADAS skill sub-package.

Each submodule exposes a small group of related ``BaseSkill`` subclasses.
The classes are intentionally NOT eagerly re-exported here — import them
from the submodule directly, e.g.::

    from domains.adas.skills.safety import HazardAnalysisSkill
    from domains.adas.skills.simulation import ScenarioGenerationSkill

This keeps the top-level import surface narrow and avoids the cost of
importing every ADAS skill just to look up one symbol.
"""
