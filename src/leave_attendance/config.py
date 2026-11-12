"""All rule numbers live here, so a viva request like "change the CL cap to 10"
is a one-line edit. Each constant notes the business rule it supports."""
from decimal import Decimal as D

# BR-01 CL: 1 per month on the 1st, max 12, lapses at year-end
CL_MONTHLY = D("1")
CL_MAX = D("12")

# BR-02 SL: 1 per month, max 12 accrued per year, carries up to 30
SL_MONTHLY = D("1")
SL_ANNUAL_ACCRUAL_MAX = D("12")
SL_CARRY_MAX = D("30")

# BR-03 EL: 1.5 per month, credited quarterly in arrears, carries up to 45
EL_MONTHLY = D("1.5")
EL_CARRY_MAX = D("45")

# BR-04 joiner in the joining month accrues only if joined on/before this day
JOINER_CUTOFF_DAY = 15

# BR-09 comp-off expires this many days after credited_on
COMP_OFF_VALIDITY_DAYS = 60

# Weekly off: Python weekday numbers (Mon=0 ... Sun=6) -> Saturday and Sunday
WEEKLY_OFF_WEEKDAYS = (5, 6)

# Used in stage 2 (leave requests); kept here so all numbers sit together
EL_NOTICE_DAYS = 7              # BR-08
SL_MEDICAL_THRESHOLD_DAYS = 3   # BR-06 (more than 3 consecutive days needs a flag)
AUTO_APPROVE_WORKING_DAYS = 5   # BR-13

LEAVE_TYPES_WITH_BALANCE = ("CL", "SL", "EL")
VALID_ATTENDANCE_STATUSES = ("P", "A", "HD", "H", "WO", "WFH")

# ---- stage 2 ----
VALID_LEAVE_TYPES = ("CL", "SL", "EL", "LOP", "COMP_OFF", "MATERNITY")
SANDWICH_LEAVE_TYPES = ("EL", "LOP")          # BR-10: off-days between leave days count
ACTIVE_STATUSES = ("PENDING", "APPROVED", "AUTO_APPROVED")
COVERING_STATUSES = ("APPROVED", "AUTO_APPROVED")   # only these cover an 'A' day
REJECT_OVERLAPPING_REQUESTS = True            # decision D-18

# ---- payroll (stage 3) ----
# Payslip `lop_days` shows LOP leave + unauthorised absences (decision D-10; ask trainers)
PAYSLIP_LOP_INCLUDES_UNAUTHORISED = True
PAYSLIP_LOP_INCLUDES_HALF_DAY = False
