from app.database import initialize_database, list_beneficiaries, match_beneficiary
initialize_database()
expected = {"AS-102", "AS-205", "AS-118", "AS-211", "AS-136", "AS-223"}
assert expected <= {b["beneficiary_id"] for b in list_beneficiaries()}
assert match_beneficiary("AS 102")["matches"][0]["name"] == "Meena Kumari"
assert match_beneficiary("ASHA 103")["matches"][0]["name"] == "Meena"
assert match_beneficiary(beneficiary_name="Lakshmi")["status"] == "ambiguous"
print("PASS: demo records, ID normalization, and ambiguous-name handling")
