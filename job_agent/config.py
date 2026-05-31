JOB_ROLES = [
    "DevOps Engineer",
    "Site Reliability Engineer",
    "IT Admin",
    "IT Administrator",
    "System Engineer",
    "System Administrator",
    "Network Engineer",
    "Lead Engineer",
]

LOCATIONS = ["Hyderabad", "Bangalore"]

# LinkedIn industry names that should be excluded
EXCLUDED_INDUSTRIES_EXACT = {
    "Staffing and Recruiting",
    "Human Resources",
    "IT Services and IT Consulting",
    "Computer and Network Security",
    "Business Consulting and Services",
    "Outsourcing and Offshoring Consulting",
    "Professional Training and Coaching",
    "Temporary Help Services",
}

# Substring keywords for fuzzy industry matching (lowercased)
EXCLUDED_INDUSTRY_KEYWORDS = [
    "staffing",
    "recruiting",
    "recruitment",
    "hr services",
    "hr consulting",
    "human resource",
    "it services",
    "it consulting",
    "it staffing",
    "outsourcing",
    "offshoring",
    "body shopping",
    "cybersecurity consulting",
    "security consulting",
    "business consulting",
    "management consulting",
    "placement services",
    "manpower",
    "headhunting",
    "talent acquisition",
    "executive search",
    "hiring services",
]

# Company size: only allow companies with ≤ 500 employees.
# LinkedIn reports sizes as ranges; we allow any range whose lower bound ≤ 500.
MAX_COMPANY_SIZE_LOWER_BOUND = 500
