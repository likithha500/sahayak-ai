
from app.safety import detect_danger_signs


def main():
    cases = [
        (
            "Pregnant woman has bleeding",
            "pregnancy_bleeding",
        ),
        (
            "Newborn has high fever",
            "newborn_high_fever",
        ),
        (
            "Newborn temperature is 38.5 C",
            "newborn_high_fever",
        ),
    ]

    for transcript, expected in cases:
        alerts = detect_danger_signs(transcript)

        assert any(
            alert["danger_type"] == expected
            for alert in alerts
        ), f"Failed: {transcript}"

        print(f"PASS: {transcript}")

    print("\nALL SAFETY TESTS PASSED")


if __name__ == "__main__":
    main()
