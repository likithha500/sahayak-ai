"""Run with: python test_safety.py (from backend directory)."""
from app.safety import detect_danger_signs


def main():
    positive = [
        ("Pregnant woman has bleeding", "pregnancy_bleeding"),
        ("Newborn has high fever", "newborn_high_fever"),
        ("Newborn temperature is 38.5 C", "newborn_high_fever"),
        ("Newborn temperature 37.5 C", "newborn_high_fever"),
        ("Newborn temperature 99.5 F", "newborn_high_fever"),
        ("Newborn temperature 35.0 C", "newborn_low_temperature"),
        ("Pregnant woman having convulsions", "pregnancy_convulsions"),
        ("Pregnant mother severe headache and blurred vision", "pregnancy_headache_vision"),
        ("Pregnant mother reports baby not moving", "pregnancy_reduced_fetal_movement"),
        ("Pregnant mother reports no fetal movement", "pregnancy_reduced_fetal_movement"),
        ("Pregnant woman leaking fluid", "pregnancy_fluid_leak"),
        ("Newborn is not feeding", "newborn_feeding_difficulty"),
        ("Newborn breathing rate 65 per minute", "newborn_breathing_difficulty"),
        ("Newborn has severe chest indrawing", "newborn_chest_indrawing"),
        ("Newborn has convulsions", "newborn_convulsions"),
        ("Postpartum mother has heavy bleeding", "postpartum_excessive_bleeding"),
        ("After childbirth mother has fits", "postpartum_convulsions"),
        ("After delivery mother has difficulty breathing", "postpartum_breathing_difficulty"),
    ]
    negative = [
        ("Pregnant woman has no bleeding", "pregnancy_bleeding"),
        ("Newborn has no fever", "newborn_high_fever"),
        ("Newborn temperature 37.0 C", "newborn_high_fever"),
        ("Newborn temperature 36.5 C", "newborn_low_temperature"),
        ("Newborn breathing rate 45 per minute", "newborn_breathing_difficulty"),
        ("Pregnant woman has a mild headache", "pregnancy_headache_vision"),
        ("Lakshmi newborn visit weight 2.8 kg", "newborn_high_fever"),
        ("Patient has fever", "newborn_high_fever"),
    ]
    for transcript, expected in positive:
        types = {a["danger_type"] for a in detect_danger_signs(transcript)}
        assert expected in types, f"Expected {expected} for {transcript!r}, got {types}"
        print(f"PASS (+): {transcript}")
    for transcript, unexpected in negative:
        types = {a["danger_type"] for a in detect_danger_signs(transcript)}
        assert unexpected not in types, f"Unexpected {unexpected} for {transcript!r}"
        print(f"PASS (-): {transcript}")
    assert "newborn_feeding_difficulty" in {
        a["danger_type"] for a in detect_danger_signs("Unable to breastfeed", visit_type="newborn")
    }
    print("PASS: prior visit context")
    print("\nALL SAFETY TESTS PASSED")


if __name__ == "__main__":
    main()
