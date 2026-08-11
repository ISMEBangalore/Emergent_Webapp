"""Generate a realistic sample Leads dump (.xlsx) matching the reference report."""
import os
import random
import pandas as pd

random.seed(7)

DIST = {
    "APPLIED": (14, 41, 71),
    "COLD Unverified leads": (1399, 3017, 10591),
    "COLD Verified leads (includes NI)": (462, 1086, 1162),
    "JOINED IN ANOTHER COLLEGE": (198, 274, 225),
    "UNANSWERED 3 TIMES": (208, 627, 204),
    "JUNK": (174, 305, 540),
    "NOT ELIGIBLE": (39, 69, 115),
    "NOT REACHABLE/SWITCH OFF": (113, 184, 982),
    "Untouched": (85, 141, 43),
    "WARM": (2, 3, 19),
}
PROGRAMS = ["B.Com", "BBA", "PGDM"]


def bucket_to_raw(bucket):
    return {
        "APPLIED": ("APPLIED", True),
        "COLD Unverified leads": ("COLD", False),
        "COLD Verified leads (includes NI)": ("COLD", True),
        "JOINED IN ANOTHER COLLEGE": ("JOINED IN OTHER COLLEGE", False),
        "UNANSWERED 3 TIMES": ("UNANSWERED 3 TIMES", False),
        "JUNK": ("JUNK", False),
        "NOT ELIGIBLE": ("NOT ELIGIBLE", False),
        "NOT REACHABLE/SWITCH OFF": ("NOT REACHABLE/SWITCH OFF", False),
        "Untouched": ("", False),
        "WARM": ("WARM", True),
    }[bucket]


rows = []
uid = 10000
for bucket, counts in DIST.items():
    raw, verified_bucket = bucket_to_raw(bucket)
    for pi, prog in enumerate(PROGRAMS):
        for _ in range(counts[pi]):
            uid += 1
            is_verified = verified_bucket or (random.random() < 0.02)
            origin = random.choices(["API Lead", "Redirect", "Organic"], weights=[0.55, 0.02, 0.43])[0]
            publisher = random.choices(
                ["Collegedunia", "Shiksha", "CollegeSearch", "Google Ads", "Meta Ads", "Organic/Direct", "Sulekha"],
                weights=[0.28, 0.20, 0.12, 0.15, 0.13, 0.08, 0.04],
            )[0]
            rows.append({
                "Registered Name": f"Applicant {uid}",
                "Course": prog,
                "Lead Stage": raw,
                "First Lead Stage": raw or "NEW",
                "Email Verification Status": "VERIFIED" if is_verified else "NOT VERIFIED",
                "Mobile Verification Status": "VERIFIED" if is_verified else "NOT VERIFIED",
                "Lead Origin(Primary)": origin,
                "Publisher Name": publisher,
                "Agent Code": f"AG{random.randint(100,140)}" if random.random() < 0.4 else "",
                "Lead Id": f"LID{uid}",
            })

random.shuffle(rows)
df = pd.DataFrame(rows)
os.makedirs("/app/backend/sample_data", exist_ok=True)
df.to_excel("/app/backend/sample_data/sample_leads.xlsx", index=False)
print("rows", len(df), "publishers:", df["Publisher Name"].nunique())
