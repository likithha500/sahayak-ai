
from app.database import (
    initialize_database,
    list_beneficiaries,
    match_beneficiary,
)


def main():
    initialize_database()

    print("\nALL BENEFICIARIES")
    for beneficiary in list_beneficiaries():
        print(beneficiary)

    print("\nTEST 1: Match by ID and name")
    print(match_beneficiary("ASHA102", "Lakshmi"))

    print("\nTEST 2: Ambiguous name")
    print(match_beneficiary(beneficiary_name="Lakshmi"))

    print("\nTEST 3: Unknown beneficiary")
    print(match_beneficiary(beneficiary_name="Priya"))

    print("\nTEST 4: Conflicting ID and name")
    print(match_beneficiary("ASHA102", "Meena"))


if __name__ == "__main__":
    main()
