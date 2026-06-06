"""
scenario_engine.py — Nonull ADAS Scenario Engine

36 built-in ADAS driving scenarios across 6 operational domains.
Scenarios are tagged, categorized, and ready for coverage analysis.
"""

from __future__ import annotations

import json
import random
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


# ──────────────────────────────────────────────────────────────
#  Domain / Category taxonomy
# ──────────────────────────────────────────────────────────────

class OperationalDomain(str, Enum):
    """SAE J3016 operational domains mapped to scenario categories."""
    HIGHWAY = "highway"
    URBAN = "urban"
    PARKING = "parking_low_speed"
    WEATHER_ENVIRONMENT = "weather_environment"
    EMERGENCY_HAZARD = "emergency_hazard"
    EDGE_CASE = "edge_case"


DOMAIN_LABELS: Dict[OperationalDomain, str] = {
    OperationalDomain.HIGHWAY: "Highway Driving",
    OperationalDomain.URBAN: "Urban / City Driving",
    OperationalDomain.PARKING: "Parking & Low Speed",
    OperationalDomain.WEATHER_ENVIRONMENT: "Weather & Environment",
    OperationalDomain.EMERGENCY_HAZARD: "Emergency & Hazard",
    OperationalDomain.EDGE_CASE: "Edge Case / Corner Case",
}


class DifficultyLevel(str, Enum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"
    EXTREME = "extreme"


# ──────────────────────────────────────────────────────────────
#  Scenario definition
# ──────────────────────────────────────────────────────────────

@dataclass
class ADASScenario:
    """A single ADAS driving scenario definition."""

    id: str                      # unique short identifier
    name: str                    # human-readable name
    domain: OperationalDomain    # which operational domain
    difficulty: DifficultyLevel  # difficulty rating
    description: str             # what happens in this scenario
    required_sensors: List[str]  # e.g. camera, radar, lidar, ultrasonic, GPS
    required_features: List[str] # e.g. AEB, LKA, ACC, TSR, BSD
    tags: List[str]              # freeform tags for search / grouping
    typical_speed_range_kmh: Tuple[int, int] = (0, 0)
    is_edge_case: bool = False
    is_weather_dependent: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "domain": self.domain.value,
            "difficulty": self.difficulty.value,
            "description": self.description,
            "required_sensors": list(self.required_sensors),
            "required_features": list(self.required_features),
            "tags": list(self.tags),
            "speed_range_kmh": list(self.typical_speed_range_kmh),
            "is_edge_case": self.is_edge_case,
            "is_weather_dependent": self.is_weather_dependent,
        }


# ──────────────────────────────────────────────────────────────
#  36 built-in scenarios
# ──────────────────────────────────────────────────────────────

def _all_scenarios() -> List[ADASScenario]:
    """Return the canonical list of 36 built-in ADAS scenarios."""
    s: List[ADASScenario] = []

    # ── Highway (8) ──────────────────────────────────────────
    s.append(ADASScenario(
        id="hw-cruise",
        name="Highway Cruise",
        domain=OperationalDomain.HIGHWAY,
        difficulty=DifficultyLevel.EASY,
        description="Steady-state highway cruising with lane keeping and adaptive cruise control at constant speed.",
        required_sensors=["camera", "radar"],
        required_features=["ACC", "LKA"],
        tags=["highway", "cruise", "lane_keeping", "constant_speed"],
        typical_speed_range_kmh=(80, 130),
    ))
    s.append(ADASScenario(
        id="hw-merge",
        name="Highway Merge",
        domain=OperationalDomain.HIGHWAY,
        difficulty=DifficultyLevel.MEDIUM,
        description="Merging onto a highway from an on-ramp. Must match highway speed and find a safe gap.",
        required_sensors=["camera", "radar"],
        required_features=["ACC", "BSM"],
        tags=["highway", "merge", "on_ramp", "gap_detection"],
        typical_speed_range_kmh=(60, 120),
    ))
    s.append(ADASScenario(
        id="hw-exit",
        name="Highway Exit",
        domain=OperationalDomain.HIGHWAY,
        difficulty=DifficultyLevel.MEDIUM,
        description="Exiting the highway onto an off-ramp. Decelerate and navigate the taper.",
        required_sensors=["camera", "radar", "GPS"],
        required_features=["ACC", "LKA", "Navigation"],
        tags=["highway", "exit", "off_ramp", "deceleration"],
        typical_speed_range_kmh=(60, 120),
    ))
    s.append(ADASScenario(
        id="hw-lane-change",
        name="Lane Change",
        domain=OperationalDomain.HIGHWAY,
        difficulty=DifficultyLevel.MEDIUM,
        description="Automatic lane change on a multi-lane highway. Check blind spot and execute.",
        required_sensors=["camera", "radar", "ultrasonic"],
        required_features=["BSM", "LCA"],
        tags=["highway", "lane_change", "blind_spot", "maneuver"],
        typical_speed_range_kmh=(60, 130),
    ))
    s.append(ADASScenario(
        id="hw-cut-in",
        name="Cut-In",
        domain=OperationalDomain.HIGHWAY,
        difficulty=DifficultyLevel.HARD,
        description="Another vehicle cuts sharply into the ego lane from an adjacent lane. Must yield safely.",
        required_sensors=["camera", "radar"],
        required_features=["ACC", "AEB", "FCW"],
        tags=["highway", "cut_in", "yield", "reactive"],
        typical_speed_range_kmh=(60, 130),
        is_edge_case=True,
    ))
    s.append(ADASScenario(
        id="hw-cut-out",
        name="Cut-Out",
        domain=OperationalDomain.HIGHWAY,
        difficulty=DifficultyLevel.MEDIUM,
        description="A lead vehicle suddenly changes out of the ego lane, revealing a stationary or slower obstacle ahead.",
        required_sensors=["camera", "radar", "lidar"],
        required_features=["ACC", "AEB", "FCW"],
        tags=["highway", "cut_out", "obstacle_reveal", "reactive"],
        typical_speed_range_kmh=(60, 130),
    ))
    s.append(ADASScenario(
        id="hw-emergency-brake",
        name="Emergency Brake",
        domain=OperationalDomain.HIGHWAY,
        difficulty=DifficultyLevel.EXTREME,
        description="Full emergency braking from highway speed to avoid a stationary obstacle or sudden deceleration ahead.",
        required_sensors=["camera", "radar", "lidar"],
        required_features=["AEB", "FCW"],
        tags=["highway", "emergency_brake", "collision_avoidance", "critical"],
        typical_speed_range_kmh=(80, 130),
        is_edge_case=True,
    ))
    s.append(ADASScenario(
        id="hw-overtaking",
        name="Overtaking",
        domain=OperationalDomain.HIGHWAY,
        difficulty=DifficultyLevel.HARD,
        description="Overtake a slower vehicle on a multi-lane highway: lane change, pass, and return.",
        required_sensors=["camera", "radar"],
        required_features=["ACC", "LCA", "BSM"],
        tags=["highway", "overtaking", "passing", "maneuver"],
        typical_speed_range_kmh=(80, 140),
    ))

    # ── Urban (8) ─────────────────────────────────────────────
    s.append(ADASScenario(
        id="urb-cruise",
        name="City Cruise",
        domain=OperationalDomain.URBAN,
        difficulty=DifficultyLevel.MEDIUM,
        description="Urban stop-and-go driving with pedestrians, cyclists, and intersections.",
        required_sensors=["camera", "radar", "ultrasonic"],
        required_features=["ACC", "AEB", "TSR"],
        tags=["urban", "cruise", "stop_and_go", "mixed_traffic"],
        typical_speed_range_kmh=(0, 60),
    ))
    s.append(ADASScenario(
        id="urb-intersection-straight",
        name="Intersection Crossing",
        domain=OperationalDomain.URBAN,
        difficulty=DifficultyLevel.MEDIUM,
        description="Crossing a signalized intersection straight through. Respond to traffic lights and crossing traffic.",
        required_sensors=["camera", "radar"],
        required_features=["TSR", "AEB"],
        tags=["urban", "intersection", "traffic_light", "straight"],
        typical_speed_range_kmh=(0, 60),
    ))
    s.append(ADASScenario(
        id="urb-left-turn",
        name="Left Turn",
        domain=OperationalDomain.URBAN,
        difficulty=DifficultyLevel.HARD,
        description="Left turn across oncoming traffic at a signalized or unsignalized intersection.",
        required_sensors=["camera", "radar"],
        required_features=["TSR", "AEB", "FCW"],
        tags=["urban", "intersection", "left_turn", "oncoming_traffic"],
        typical_speed_range_kmh=(0, 40),
    ))
    s.append(ADASScenario(
        id="urb-right-turn",
        name="Right Turn",
        domain=OperationalDomain.URBAN,
        difficulty=DifficultyLevel.MEDIUM,
        description="Right turn at an intersection, yielding to pedestrians and cyclists in the crosswalk.",
        required_sensors=["camera", "radar", "ultrasonic"],
        required_features=["AEB", "BSD"],
        tags=["urban", "intersection", "right_turn", "pedestrian"],
        typical_speed_range_kmh=(0, 30),
    ))
    s.append(ADASScenario(
        id="urb-roundabout",
        name="Roundabout",
        domain=OperationalDomain.URBAN,
        difficulty=DifficultyLevel.HARD,
        description="Navigate a multi-lane roundabout: yield on entry, maintain lane, exit correctly.",
        required_sensors=["camera", "radar"],
        required_features=["Navigation", "BSM"],
        tags=["urban", "roundabout", "yield", "navigation"],
        typical_speed_range_kmh=(10, 40),
    ))
    s.append(ADASScenario(
        id="urb-pedestrian",
        name="Pedestrian Crossing",
        domain=OperationalDomain.URBAN,
        difficulty=DifficultyLevel.HARD,
        description="Pedestrian steps into crosswalk unexpectedly. Must detect and brake in time.",
        required_sensors=["camera", "radar", "lidar"],
        required_features=["AEB", "FCW", "PedestrianDetection"],
        tags=["urban", "pedestrian", "crosswalk", "vulnerable_road_user"],
        typical_speed_range_kmh=(0, 50),
        is_edge_case=True,
    ))
    s.append(ADASScenario(
        id="urb-cyclist",
        name="Cyclist Awareness",
        domain=OperationalDomain.URBAN,
        difficulty=DifficultyLevel.HARD,
        description="Cyclist riding alongside or ahead. Maintain safe distance and anticipate sudden movements.",
        required_sensors=["camera", "radar"],
        required_features=["BSD", "AEB", "CyclistDetection"],
        tags=["urban", "cyclist", "vulnerable_road_user", "proximity"],
        typical_speed_range_kmh=(10, 50),
    ))
    s.append(ADASScenario(
        id="urb-school-zone",
        name="School Zone",
        domain=OperationalDomain.URBAN,
        difficulty=DifficultyLevel.MEDIUM,
        description="Drive through a school zone with reduced speed limit, children near roadway, and crossing guards.",
        required_sensors=["camera", "GPS"],
        required_features=["TSR", "AEB"],
        tags=["urban", "school_zone", "speed_limit", "children"],
        typical_speed_range_kmh=(0, 30),
    ))

    # ── Parking & Low Speed (4) ──────────────────────────────
    s.append(ADASScenario(
        id="prk-parallel",
        name="Parallel Parking",
        domain=OperationalDomain.PARKING,
        difficulty=DifficultyLevel.HARD,
        description="Parallel park into a tight spot between two vehicles. Multi-point maneuver.",
        required_sensors=["camera", "ultrasonic"],
        required_features=["ParkAssist", "Ultrasonic"],
        tags=["parking", "parallel", "tight_spot", "maneuver"],
        typical_speed_range_kmh=(0, 10),
    ))
    s.append(ADASScenario(
        id="prk-perpendicular",
        name="Perpendicular Parking",
        domain=OperationalDomain.PARKING,
        difficulty=DifficultyLevel.MEDIUM,
        description="Reverse or forward park into a perpendicular bay. Handle bay detection.",
        required_sensors=["camera", "ultrasonic"],
        required_features=["ParkAssist", "RearCamera"],
        tags=["parking", "perpendicular", "bay_parking", "reverse"],
        typical_speed_range_kmh=(0, 10),
    ))
    s.append(ADASScenario(
        id="prk-valet",
        name="Valet Parking",
        domain=OperationalDomain.PARKING,
        difficulty=DifficultyLevel.EXTREME,
        description="Full automated valet: navigate a parking structure, find a spot, park, and return on call.",
        required_sensors=["camera", "radar", "ultrasonic", "lidar"],
        required_features=["ParkAssist", "Navigation", "RemotePark"],
        tags=["parking", "valet", "automated", "garage"],
        typical_speed_range_kmh=(0, 15),
    ))
    s.append(ADASScenario(
        id="prk-traffic-jam",
        name="Traffic Jam Assist",
        domain=OperationalDomain.PARKING,
        difficulty=DifficultyLevel.MEDIUM,
        description="Stop-and-go traffic jam at low speed. Maintain safe distance and creep forward automatically.",
        required_sensors=["camera", "radar", "ultrasonic"],
        required_features=["ACC", "AEB", "TJA"],
        tags=["parking", "traffic_jam", "stop_go", "low_speed"],
        typical_speed_range_kmh=(0, 30),
    ))

    # ── Weather & Environment (6) ────────────────────────────
    s.append(ADASScenario(
        id="wth-rain",
        name="Rain Driving",
        domain=OperationalDomain.WEATHER_ENVIRONMENT,
        difficulty=DifficultyLevel.HARD,
        description="Heavy rain reducing visibility and road friction. Hydroplaning risk.",
        required_sensors=["camera", "radar"],
        required_features=["ACC", "LKA", "RainSensor"],
        tags=["weather", "rain", "low_friction", "reduced_visibility"],
        typical_speed_range_kmh=(40, 100),
        is_weather_dependent=True,
    ))
    s.append(ADASScenario(
        id="wth-night",
        name="Night Driving",
        domain=OperationalDomain.WEATHER_ENVIRONMENT,
        difficulty=DifficultyLevel.MEDIUM,
        description="Driving after dark with limited illumination. Relies on headlights and IR sensors.",
        required_sensors=["camera", "radar", "lidar"],
        required_features=["ACC", "LKA", "AEB", "NightVision"],
        tags=["weather", "night", "low_light", "darkness"],
        typical_speed_range_kmh=(0, 120),
        is_weather_dependent=True,
    ))
    s.append(ADASScenario(
        id="wth-fog",
        name="Fog Driving",
        domain=OperationalDomain.WEATHER_ENVIRONMENT,
        difficulty=DifficultyLevel.EXTREME,
        description="Dense fog with visibility below 50 m. Camera performance degrades significantly.",
        required_sensors=["radar", "lidar"],
        required_features=["ACC", "AEB", "FCW"],
        tags=["weather", "fog", "very_low_visibility", "sensor_limitation"],
        typical_speed_range_kmh=(20, 60),
        is_weather_dependent=True,
        is_edge_case=True,
    ))
    s.append(ADASScenario(
        id="wth-snow",
        name="Snow / Ice",
        domain=OperationalDomain.WEATHER_ENVIRONMENT,
        difficulty=DifficultyLevel.EXTREME,
        description="Snow-covered roads with reduced traction, obscured lane markings, and blowing snow.",
        required_sensors=["camera", "radar", "lidar"],
        required_features=["ACC", "AEB", "TCS", "ABS"],
        tags=["weather", "snow", "ice", "low_traction", "obscured_markings"],
        typical_speed_range_kmh=(0, 60),
        is_weather_dependent=True,
        is_edge_case=True,
    ))
    s.append(ADASScenario(
        id="wth-glare",
        name="Low Sun Glare",
        domain=OperationalDomain.WEATHER_ENVIRONMENT,
        difficulty=DifficultyLevel.HARD,
        description="Driving directly into a low sun. Camera sensor saturation causes temporary blindness.",
        required_sensors=["radar", "lidar"],
        required_features=["ACC", "AEB"],
        tags=["weather", "sun_glare", "sensor_saturation", "low_sun"],
        typical_speed_range_kmh=(0, 100),
        is_weather_dependent=True,
        is_edge_case=True,
    ))
    s.append(ADASScenario(
        id="wth-tunnel",
        name="Tunnel Transition",
        domain=OperationalDomain.WEATHER_ENVIRONMENT,
        difficulty=DifficultyLevel.MEDIUM,
        description="Entering or exiting a tunnel. Sudden illumination change and GPS signal loss.",
        required_sensors=["camera", "radar"],
        required_features=["ACC", "LKA", "GPS"],
        tags=["weather", "tunnel", "illumination_change", "gps_loss"],
        typical_speed_range_kmh=(40, 100),
        is_weather_dependent=True,
    ))

    # ── Emergency & Hazard (5) ───────────────────────────────
    s.append(ADASScenario(
        id="haz-animal",
        name="Animal Crossing",
        domain=OperationalDomain.EMERGENCY_HAZARD,
        difficulty=DifficultyLevel.EXTREME,
        description="Large animal (deer, moose) suddenly enters the roadway. Emergency braking or evasive steering required.",
        required_sensors=["camera", "radar", "lidar"],
        required_features=["AEB", "FCW", "AnimalDetection"],
        tags=["hazard", "animal", "unexpected_obstacle", "evasive"],
        typical_speed_range_kmh=(30, 100),
        is_edge_case=True,
    ))
    s.append(ADASScenario(
        id="haz-debris",
        name="Debris Avoidance",
        domain=OperationalDomain.EMERGENCY_HAZARD,
        difficulty=DifficultyLevel.EXTREME,
        description="Obstacle or debris (tire, cargo, fallen branch) in the travel lane. Must detect and avoid.",
        required_sensors=["camera", "radar", "lidar"],
        required_features=["AEB", "FCW"],
        tags=["hazard", "debris", "obstacle_avoidance", "unexpected"],
        typical_speed_range_kmh=(30, 120),
        is_edge_case=True,
    ))
    s.append(ADASScenario(
        id="haz-construction",
        name="Construction Zone",
        domain=OperationalDomain.EMERGENCY_HAZARD,
        difficulty=DifficultyLevel.HARD,
        description="Navigate a work zone with cones, barrels, temporary signage, and lane shifts.",
        required_sensors=["camera", "radar", "GPS"],
        required_features=["TSR", "LKA", "Navigation"],
        tags=["hazard", "construction", "work_zone", "lane_shift"],
        typical_speed_range_kmh=(0, 80),
    ))
    s.append(ADASScenario(
        id="haz-accident",
        name="Accident Scene",
        domain=OperationalDomain.EMERGENCY_HAZARD,
        difficulty=DifficultyLevel.EXTREME,
        description="Approach an accident scene with stopped vehicles, emergency responders, and debris.",
        required_sensors=["camera", "radar", "lidar"],
        required_features=["AEB", "FCW", "V2X"],
        tags=["hazard", "accident", "emergency_responders", "obstacle"],
        typical_speed_range_kmh=(0, 80),
        is_edge_case=True,
    ))
    s.append(ADASScenario(
        id="haz-flooded",
        name="Flooded Roadway",
        domain=OperationalDomain.EMERGENCY_HAZARD,
        difficulty=DifficultyLevel.HARD,
        description="Water accumulation on the roadway. Assess depth, avoid hydro-lock, and reroute if needed.",
        required_sensors=["camera", "radar", "GPS"],
        required_features=["Navigation", "AEB"],
        tags=["hazard", "flood", "water", "reroute"],
        typical_speed_range_kmh=(0, 30),
        is_weather_dependent=True,
        is_edge_case=True,
    ))

    # ── Edge Cases / Corner Cases (5) ────────────────────────
    s.append(ADASScenario(
        id="edg-ghost-brake",
        name="Ghost Braking",
        domain=OperationalDomain.EDGE_CASE,
        difficulty=DifficultyLevel.HARD,
        description="False positive braking triggered by shadow, bridge joint, or overpass misinterpreted as obstacle.",
        required_sensors=["camera", "radar"],
        required_features=["AEB", "FCW"],
        tags=["edge", "false_positive", "ghost_braking", "nuisance"],
        typical_speed_range_kmh=(30, 120),
        is_edge_case=True,
    ))
    s.append(ADASScenario(
        id="edg-faded-markings",
        name="Faded Lane Markings",
        domain=OperationalDomain.EDGE_CASE,
        difficulty=DifficultyLevel.HARD,
        description="Lane markings worn, faded, or obscured by snow/leaves. LKA degrades or fails.",
        required_sensors=["camera"],
        required_features=["LKA"],
        tags=["edge", "lane_markings", "faded", "infrastructure"],
        typical_speed_range_kmh=(0, 100),
        is_edge_case=True,
        is_weather_dependent=True,
    ))
    s.append(ADASScenario(
        id="edg-extreme-weather",
        name="Extreme Weather",
        domain=OperationalDomain.EDGE_CASE,
        difficulty=DifficultyLevel.EXTREME,
        description="Hailstorm, torrential downpour, or blizzard that overwhelms sensor and actuator capability.",
        required_sensors=["camera", "radar", "lidar"],
        required_features=["ACC", "AEB"],
        tags=["edge", "extreme_weather", "sensor_overload", "minimal_risk"],
        typical_speed_range_kmh=(0, 40),
        is_edge_case=True,
        is_weather_dependent=True,
    ))
    s.append(ADASScenario(
        id="edg-complex-intersection",
        name="Complex Intersection",
        domain=OperationalDomain.EDGE_CASE,
        difficulty=DifficultyLevel.EXTREME,
        description="Unmarked or poorly marked intersection, multi-lane crossing with no traffic lights,混杂 traffic patterns.",
        required_sensors=["camera", "radar", "lidar"],
        required_features=["TSR", "AEB", "Navigation"],
        tags=["edge", "intersection", "unmarked", "complex"],
        typical_speed_range_kmh=(0, 30),
        is_edge_case=True,
    ))
    s.append(ADASScenario(
        id="edg-sensor-failure",
        name="Sensor Degradation",
        domain=OperationalDomain.EDGE_CASE,
        difficulty=DifficultyLevel.EXTREME,
        description="Partial sensor failure (camera blocked, radar misaligned). System must degrade gracefully and hand over to driver.",
        required_sensors=["camera", "radar", "lidar"],
        required_features=["ACC", "LKA", "AEB", "FailSafe"],
        tags=["edge", "sensor_failure", "graceful_degradation", "handover"],
        typical_speed_range_kmh=(0, 130),
        is_edge_case=True,
    ))

    return s


# ──────────────────────────────────────────────────────────────
#  ScenarioEngine — core class
# ──────────────────────────────────────────────────────────────

class ScenarioEngine:
    """Maps driving tasks to ADAS scenarios and provides coverage analysis."""

    def __init__(self) -> None:
        self._scenarios: List[ADASScenario] = _all_scenarios()
        self._by_id: Dict[str, ADASScenario] = {}
        self._build_index()

    def _build_index(self) -> None:
        for sc in self._scenarios:
            self._by_id[sc.id] = sc

    # ── Accessors ────────────────────────────────────────────

    @property
    def scenarios(self) -> List[ADASScenario]:
        """Return all 36 scenarios."""
        return list(self._scenarios)

    def get(self, scenario_id: str) -> ADASScenario:
        """Look up a single scenario by its ID."""
        if scenario_id not in self._by_id:
            raise KeyError(f"Unknown scenario ID: {scenario_id!r}")
        return self._by_id[scenario_id]

    def by_domain(self, domain: OperationalDomain) -> List[ADASScenario]:
        """Filter scenarios by operational domain."""
        return [s for s in self._scenarios if s.domain == domain]

    def by_difficulty(self, level: DifficultyLevel) -> List[ADASScenario]:
        """Filter scenarios by difficulty level."""
        return [s for s in self._scenarios if s.difficulty == level]

    def by_tag(self, tag: str) -> List[ADASScenario]:
        """Filter scenarios that have the given tag."""
        return [s for s in self._scenarios if tag in s.tags]

    def by_feature(self, feature: str) -> List[ADASScenario]:
        """Filter scenarios that require a specific ADAS feature."""
        return [s for s in self._scenarios if feature in s.required_features]

    def by_sensor(self, sensor: str) -> List[ADASScenario]:
        """Filter scenarios that require a specific sensor."""
        return [s for s in self._scenarios if sensor in s.required_sensors]

    # ── Task-to-scenario mapping ─────────────────────────────

    # ── Convenience aliases for orchestrator / external callers ──

    def analyze_task_scenarios(self, task_description: str) -> List[ADASScenario]:
        """Alias for :meth:`map_task` (used by PersonaOrchestrator)."""
        return self.map_task(task_description)

    def analyze_scenario_coverage(
        self, test_cases: list
    ) -> Dict[str, Any]:
        """
        Alias for :meth:`coverage_analysis` accepting a list of test cases.

        Test cases can be either:
          - scenario IDs (str)
          - dicts with an ``id`` key
          - ADASScenario instances
        """
        covered_ids: List[str] = []
        for tc in test_cases or []:
            if isinstance(tc, str):
                covered_ids.append(tc)
            elif isinstance(tc, ADASScenario):
                covered_ids.append(tc.id)
            elif isinstance(tc, dict) and "id" in tc:
                covered_ids.append(tc["id"])
        return self.coverage_analysis(covered_ids)

    def map_task(self, task_description: str) -> List[ADASScenario]:
        """Map a free-text driving task to the most relevant scenarios.

        Uses keyword matching against scenario names, tags, and descriptions.
        Returns all matches ranked by relevance score.
        """
        task_lower = task_description.lower()
        tokens = {tok for tok in task_lower.split() if len(tok) > 2}

        scored: List[Tuple[int, ADASScenario]] = []
        for sc in self._scenarios:
            score = 0
            # Exact name match
            if task_lower in sc.name.lower():
                score += 10
            # Tag hits
            for tag in sc.tags:
                if tag.lower() in task_lower or any(t in tag.lower() for t in tokens):
                    score += 5
            # Description hits
            for word in tokens:
                if word in sc.description.lower():
                    score += 2
                if word in sc.name.lower():
                    score += 3
            # Feature / sensor mentions
            for f in sc.required_features:
                if f.lower() in task_lower:
                    score += 4
            for sens in sc.required_sensors:
                if sens.lower() in task_lower:
                    score += 4
            if score > 0:
                scored.append((score, sc))

        scored.sort(key=lambda x: -x[0])
        return [sc for _, sc in scored]

    def map_domain_task(self, domain: OperationalDomain, task_description: str) -> List[ADASScenario]:
        """Map a task but restrict matches to a specific operational domain."""
        domain_scenarios = self.by_domain(domain)
        task_lower = task_description.lower()

        scored: List[Tuple[int, ADASScenario]] = []
        for sc in domain_scenarios:
            score = 0
            if task_lower in sc.name.lower():
                score += 10
            for tag in sc.tags:
                if tag.lower() in task_lower:
                    score += 5
            for word in task_lower.split():
                if len(word) > 2 and word in sc.description.lower():
                    score += 2
            if score > 0:
                scored.append((score, sc))

        scored.sort(key=lambda x: -x[0])
        return [sc for _, sc in scored]

    # ── Coverage analysis ────────────────────────────────────

    def coverage_analysis(self, covered_ids: List[str]) -> Dict[str, Any]:
        """Analyze scenario coverage.

        Parameters
        ----------
        covered_ids : list of str
            The scenario IDs that the system under test has passed / covered.

        Returns
        -------
        dict with coverage stats, missing scenarios, and breakdowns.
        """
        covered_set = set(covered_ids)
        all_ids = {s.id for s in self._scenarios}

        covered = [s for s in self._scenarios if s.id in covered_set]
        missing = [s for s in self._scenarios if s.id not in covered_set]

        total = len(self._scenarios)
        n_covered = len(covered)
        coverage_pct = round(n_covered / total * 100, 1) if total else 0.0

        # Per-domain breakdown
        domain_breakdown = {}
        for domain in OperationalDomain:
            domain_scenarios = self.by_domain(domain)
            dom_total = len(domain_scenarios)
            dom_covered_ids = {s.id for s in domain_scenarios if s.id in covered_set}
            dom_covered = len(dom_covered_ids)
            domain_breakdown[domain.value] = {
                "label": DOMAIN_LABELS[domain],
                "total": dom_total,
                "covered": dom_covered,
                "missing": dom_total - dom_covered,
                "coverage_pct": round(dom_covered / dom_total * 100, 1) if dom_total else 0.0,
            }

        # Per-difficulty breakdown
        difficulty_breakdown = {}
        for diff in DifficultyLevel:
            diff_scenarios = self.by_difficulty(diff)
            diff_total = len(diff_scenarios)
            diff_covered_ids = {s.id for s in diff_scenarios if s.id in covered_set}
            diff_covered = len(diff_covered_ids)
            difficulty_breakdown[diff.value] = {
                "total": diff_total,
                "covered": diff_covered,
                "missing": diff_total - diff_covered,
                "coverage_pct": round(diff_covered / diff_total * 100, 1) if diff_total else 0.0,
            }

        # Edge case coverage
        edge_scenarios = [s for s in self._scenarios if s.is_edge_case]
        edge_covered = [s for s in edge_scenarios if s.id in covered_set]
        edge_missing = [s for s in edge_scenarios if s.id not in covered_set]

        # Feature coverage heatmap
        all_features = sorted({f for s in self._scenarios for f in s.required_features})
        feature_coverage: Dict[str, Dict[str, Any]] = {}
        for feat in all_features:
            feat_scenarios = self.by_feature(feat)
            feat_total = len(feat_scenarios)
            feat_covered_ids = {s.id for s in feat_scenarios if s.id in covered_set}
            feature_coverage[feat] = {
                "scenarios": len(feat_scenarios),
                "covered": len(feat_covered_ids),
                "coverage_pct": round(len(feat_covered_ids) / feat_total * 100, 1) if feat_total else 0.0,
            }

        missing_severity: Dict[str, List[Dict[str, Any]]] = {"high": [], "medium": [], "low": []}
        for sc in missing:
            if sc.is_edge_case:
                missing_severity["high"].append(sc.to_dict())
            elif sc.difficulty in (DifficultyLevel.HARD, DifficultyLevel.EXTREME):
                missing_severity["high"].append(sc.to_dict())
            elif sc.difficulty == DifficultyLevel.MEDIUM:
                missing_severity["medium"].append(sc.to_dict())
            else:
                missing_severity["low"].append(sc.to_dict())

        return {
            "total_scenarios": total,
            "covered_count": n_covered,
            "missing_count": total - n_covered,
            "coverage_pct": coverage_pct,
            "covered_scenarios": [s.to_dict() for s in covered],
            "missing_scenarios": [s.to_dict() for s in missing],
            "domain_breakdown": domain_breakdown,
            "difficulty_breakdown": difficulty_breakdown,
            "edge_case_coverage": {
                "total": len(edge_scenarios),
                "covered": len(edge_covered),
                "missing": [s.to_dict() for s in edge_missing],
            },
            "feature_coverage": feature_coverage,
            "missing_by_severity": missing_severity,
        }

    # ── Edge case suggestions ────────────────────────────────

    def suggest_edge_cases(self, covered_ids: List[str]) -> Dict[str, Any]:
        """Suggest additional edge / corner cases based on coverage."""
        covered_set = set(covered_ids)
        missing = [s for s in self._scenarios if s.id not in covered_set]

        suggestions = []
        domain_gaps = {}

        for sc in missing:
            if sc.is_edge_case or sc.difficulty in (DifficultyLevel.HARD, DifficultyLevel.EXTREME):
                suggestions.append({
                    "priority": "HIGH" if sc.is_edge_case else "MEDIUM",
                    "scenario": sc.to_dict(),
                    "reason": (
                        "Edge case scenario missing — high risk of real-world failure"
                        if sc.is_edge_case
                        else f"Uncovered {sc.difficulty.value} scenario — should be tested"
                    ),
                })

        # Domain-level gap analysis
        for sc in self._scenarios:
            dom = sc.domain.value
            if dom not in domain_gaps:
                domain_gaps[dom] = {"total": 0, "covered": 0, "missing_ids": []}
            domain_gaps[dom]["total"] += 1
            if sc.id in covered_set:
                domain_gaps[dom]["covered"] += 1
            else:
                domain_gaps[dom]["missing_ids"].append(sc.id)

        # Generate combinatorial suggestions
        combinatorial_suggestions = []
        low_coverage_domains = [
            dom for dom, stats in domain_gaps.items()
            if stats["total"] > 0 and stats["covered"] / stats["total"] < 0.5
        ]
        if low_coverage_domains:
            for dom in low_coverage_domains:
                combinatorial_suggestions.append(
                    f"Domain '{DOMAIN_LABELS.get(OperationalDomain(dom), dom)}' has <50% coverage. "
                    f"Consider additional cross-domain scenarios combining conditions from this domain "
                    f"with adverse weather or edge cases."
                )

        # Weather + scenario combinations
        weather_ids = [s.id for s in self._scenarios if s.is_weather_dependent]
        weather_covered = [wid for wid in weather_ids if wid in covered_set]
        weather_missing = len(weather_ids) - len(weather_covered)
        if weather_missing > 0:
            combinatorial_suggestions.append(
                f"{weather_missing} weather-dependent scenario(s) not covered. "
                f"Consider testing sunny-day versions of these scenarios as a baseline."
            )

        return {
            "total_edge_cases": len([s for s in self._scenarios if s.is_edge_case]),
            "uncovered_edge_cases": len([s for s in self._scenarios if s.is_edge_case and s.id not in covered_set]),
            "suggestions": suggestions,
            "combinatorial_suggestions": combinatorial_suggestions,
            "domain_gaps": {
                dom: {
                    "label": DOMAIN_LABELS.get(OperationalDomain(dom), dom),
                    "total": stats["total"],
                    "covered": stats["covered"],
                    "coverage_pct": round(stats["covered"] / stats["total"] * 100, 1) if stats["total"] else 0.0,
                }
                for dom, stats in domain_gaps.items()
            },
        }

    # ── Summary report ───────────────────────────────────────

    def summary(self) -> Dict[str, Any]:
        """Return a high-level summary of the scenario library."""
        return {
            "total_scenarios": len(self._scenarios),
            "by_domain": {
                DOMAIN_LABELS[d]: len(self.by_domain(d)) for d in OperationalDomain
            },
            "by_difficulty": {
                dl.value: len(self.by_difficulty(dl)) for dl in DifficultyLevel
            },
            "total_edge_cases": len([s for s in self._scenarios if s.is_edge_case]),
            "total_weather_dependent": len([s for s in self._scenarios if s.is_weather_dependent]),
            "required_features": sorted({f for s in self._scenarios for f in s.required_features}),
            "required_sensors": sorted({sen for s in self._scenarios for sen in s.required_sensors}),
        }

    # ── Serialization ────────────────────────────────────────

    def to_json(self, indent: int = 2) -> str:
        """Dump all scenarios as a JSON string."""
        return json.dumps(
            {"scenarios": [s.to_dict() for s in self._scenarios]},
            indent=indent,
            ensure_ascii=False,
        )


# ──────────────────────────────────────────────────────────────
#  Convenience singleton
# ──────────────────────────────────────────────────────────────

_ENGINE: Optional[ScenarioEngine] = None

def get_engine() -> ScenarioEngine:
    """Get or create the global ScenarioEngine singleton."""
    global _ENGINE
    if _ENGINE is None:
        _ENGINE = ScenarioEngine()
    return _ENGINE


# ──────────────────────────────────────────────────────────────
#  Quick self-test
# ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    engine = get_engine()

    print("=" * 60)
    print("  Nonull Scenario Engine — Self Test")
    print("=" * 60)

    summary = engine.summary()
    print(f"\nTotal scenarios: {summary['total_scenarios']}")
    print(f"By domain:")
    for label, count in summary["by_domain"].items():
        print(f"  {label}: {count}")
    print(f"\nEdge cases: {summary['total_edge_cases']}")
    print(f"Weather-dependent: {summary['total_weather_dependent']}")
    print(f"Features: {', '.join(summary['required_features'])}")
    print(f"Sensors: {', '.join(summary['required_sensors'])}")

    # Coverage analysis demo
    all_ids = [s.id for s in engine.scenarios]
    partial = random.sample(all_ids, k=20)
    coverage = engine.coverage_analysis(partial)
    print(f"\nCoverage analysis ({coverage['covered_count']}/{coverage['total_scenarios']}):")
    print(f"  Overall: {coverage['coverage_pct']}%")
    print(f"  Missing: {coverage['missing_count']} scenarios")
    for dom_key, dom_data in coverage["domain_breakdown"].items():
        print(f"  {dom_key}: {dom_data['coverage_pct']}% ({dom_data['covered']}/{dom_data['total']})")

    # Edge case suggestions
    suggestions = engine.suggest_edge_cases(partial)
    print(f"\nEdge case suggestions ({suggestions['uncovered_edge_cases']} uncovered):")
    for s in suggestions["suggestions"][:5]:
        print(f"  [{s['priority']}] {s['scenario']['name']}: {s['reason']}")
    for cs in suggestions["combinatorial_suggestions"]:
        print(f"  [COMBINATORIAL] {cs}")

    # Task mapping demo
    print("\nTask mapping for 'merge onto highway at night in rain':")
    for sc in engine.map_task("merge onto highway at night in rain"):
        print(f"  {sc.id} ({sc.name})")

    print("\n✓ Scenario Engine ready.")
