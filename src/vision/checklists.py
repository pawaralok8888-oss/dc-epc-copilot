"""Photo checklists per commissioning level.
L1: nameplate vs approved submittal (automatic, from Reality Delta).
L2: installation checks (engineer confirms from site photos).
L3-L5: no photo checklist.
"""
L2_COMMON = ["Equipment tag label matches drawings", "Anchor bolts and base fixing fitted",
             "Clearances around unit are as per layout", "Earthing connection visible and tight"]
L2_BY_SYSTEM = {
    "power": ["Cable terminations torqued and marked", "Cable entry glands sealed", "Phase labelling present"],
    "cooling": ["Pipe connections and valves fitted", "Insulation intact, no condensation marks", "Drain and vent points fitted"],
}


def level_mode(level):
    return {"L1": "auto", "L2": "manual"}.get(level, "none")


def l2_checklist(system):
    return L2_COMMON + L2_BY_SYSTEM.get(system, [])
