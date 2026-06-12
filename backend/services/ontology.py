"""
Domain-specific ontology for automotive parking requirements.
Defines concepts, relationships, and reasoning rules aligned with
ISO 26262, SAE J3016, and AUTOSAR standards.
"""

PARKING_ONTOLOGY = {
    "concepts": {
        # Core Functions
        "RemoteParkingAssist": {
            "parent": "ParkingFunction",
            "sae_level": "L2",
            "description": "Driver monitors remotely; system handles steering and speed",
            "sensors": ["UltrasonicSensor", "Camera360", "ParkingECU"],
        },
        "AutomaticParkingAssist": {
            "parent": "ParkingFunction",
            "sae_level": "L2",
            "description": "System steers into space; driver controls speed",
            "sensors": ["UltrasonicSensor", "Camera"],
        },
        "SummonFunction": {
            "parent": "ParkingFunction",
            "sae_level": "L2",
            "description": "Vehicle moves to predefined location autonomously",
            "sensors": ["UltrasonicSensor", "Camera360", "GPS"],
        },

        # Sensors
        "UltrasonicSensor": {"parent": "Sensor", "range_m": 5, "frequency_hz": 10},
        "Camera": {"parent": "Sensor", "type": "monocular"},
        "Camera360": {"parent": "Sensor", "type": "surround"},
        "Radar": {"parent": "Sensor", "range_m": 150},
        "LiDAR": {"parent": "Sensor", "range_m": 100},

        # Safety Concepts
        "ASIL_B": {"parent": "SafetyLevel", "standard": "ISO26262"},
        "ASIL_D": {"parent": "SafetyLevel", "standard": "ISO26262"},
        "QM": {"parent": "SafetyLevel", "standard": "ISO26262"},

        # Requirements Types
        "FunctionalRequirement": {"parent": "Requirement"},
        "SafetyRequirement": {"parent": "Requirement", "standard": "ISO26262"},
        "PerformanceRequirement": {"parent": "Requirement"},
        "InterfaceRequirement": {"parent": "Requirement"},

        # Actors
        "Driver": {"parent": "HumanActor"},
        "Pedestrian": {"parent": "ExternalActor"},
        "Vehicle": {"parent": "SystemEntity"},

        # Environment
        "ParkingSpace": {"parent": "Environment", "types": ["parallel", "perpendicular", "angled"]},
        "ParkingGarage": {"parent": "Environment"},
        "OpenLot": {"parent": "Environment"},
    },

    "relations": [
        ("ParkingFunction", "uses", "Sensor"),
        ("ParkingFunction", "requires", "SafetyLevel"),
        ("SafetyRequirement", "derives_from", "ISO26262"),
        ("FunctionalRequirement", "implements", "ParkingFunction"),
        ("ParkingFunction", "affects", "Driver"),
        ("ParkingFunction", "operates_in", "ParkingSpace"),
        ("UltrasonicSensor", "detects", "ParkingSpace"),
        ("Camera360", "monitors", "Environment"),
    ],

    "reasoning_rules": [
        {
            "name": "safety_propagation",
            "description": "If a function has ASIL_D requirement, all sub-functions must be at least ASIL_B",
            "antecedent": "Function hasASIL ASIL_D",
            "consequent": "SubFunction requiresMinASIL ASIL_B",
        },
        {
            "name": "sensor_redundancy",
            "description": "Safety-critical parking functions require at least 2 independent sensors",
            "antecedent": "Function isSafetyCritical true",
            "consequent": "Function requiresSensorCount >= 2",
        },
        {
            "name": "sae_level_constraint",
            "description": "L2 functions require continuous driver monitoring",
            "antecedent": "Function hasSAELevel L2",
            "consequent": "Function requires DriverMonitoring",
        },
    ],
}


def get_concept(name: str) -> dict:
    return PARKING_ONTOLOGY["concepts"].get(name, {})


def get_related_concepts(name: str) -> list:
    """Return all concepts related to a given concept via ontology relations."""
    related = []
    for src, rel, tgt in PARKING_ONTOLOGY["relations"]:
        if src == name:
            related.append({"target": tgt, "relation": rel})
        elif tgt == name:
            related.append({"target": src, "relation": f"inverse:{rel}"})
    return related


def get_applicable_rules(function_name: str) -> list:
    """Return reasoning rules applicable to a function."""
    return PARKING_ONTOLOGY["reasoning_rules"]


ALL_CONCEPTS = list(PARKING_ONTOLOGY["concepts"].keys())
ALL_RELATIONS = PARKING_ONTOLOGY["relations"]
